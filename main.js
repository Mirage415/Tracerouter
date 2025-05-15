// main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const ffmpeg = require('ffmpeg-static');

// 使用whisper-node-addon替代nodejs-whisper
// 修正导入方式与调用
const whisperModule = require('whisper-node-addon');
// 创建更健壮的转录函数包装
const whisper = {
  transcribe: async (options) => {
    return new Promise((resolve, reject) => {
      try {
        console.log('调用whisperModule.transcribe');
        // 此处检查返回类型，兼容同步/异步API
        const result = whisperModule.transcribe(options);
        if (result instanceof Promise) {
          result.then(resolve).catch(reject);
        } else {
          // 同步函数也处理
          resolve(result);
        }
      } catch (error) {
        console.error('Whisper转录错误:', error);
        reject(error);
      }
    });
  }
};

// 处理路径，确保在打包和开发环境中都能正常工作
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

// 临时文件目录
const tempDir = path.join(app.getPath('temp'), 'tracerouter');

// 确保临时目录存在
if (!fs.existsSync(tempDir)) {
  fs.mkdirSync(tempDir, { recursive: true });
  console.log(`创建临时目录: ${tempDir}`);
}

// 获取资源路径，在开发环境和打包环境下都能正常工作
function getResourcePath(relativePath) {
  if (isDev) {
    return path.join(__dirname, relativePath);
  } else {
    return path.join(process.resourcesPath, relativePath);
  }
}

// 运行Python脚本的函数
function spawnPythonProcess(scriptPath, args, event, prefix) {
  // 确定实际的Python解释器路径
  let pythonCommand = 'python3';
  if (process.platform === 'win32') {
    pythonCommand = 'python'; // Windows上通常是python而不是python3
  }

  event.sender.send('traceroute-output', `${prefix}: 正在执行${scriptPath}...\n`);

  const pythonProcess = spawn(pythonCommand, [scriptPath, ...args]);

  pythonProcess.stdout.on('data', (data) => {
    event.sender.send('traceroute-output', `${prefix}: ${data.toString()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    event.sender.send('traceroute-output', `${prefix} 错误: ${data.toString()}`);
  });

  return pythonProcess;
}
ipcMain.handle('save-option-json', async (event, content) => {
  const filePath = path.join(process.cwd(), 'option.json');
  fs.writeFileSync(filePath, content, 'utf-8');
  return true;
});
function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true
    }
  });

  win.webContents.session.setPermissionRequestHandler((webContents, permission, callback) => {
    if (permission === 'media') {
      return callback(true);
    }
    callback(false);
  });

  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  // 仅在开发环境下打开开发者工具
  if (isDev) {
    win.webContents.openDevTools();
  }
}

app.whenReady().then(() => {
  createWindow();

  // 确保应用目录存在
  const rendererDir = path.join(isDev ? __dirname : process.resourcesPath, 'renderer');
  if (!fs.existsSync(rendererDir)) {
    fs.mkdirSync(rendererDir, { recursive: true });
  }

  // 确保traceroute_results目录存在
  const resultsDir = path.join(
    isDev ? __dirname : process.resourcesPath,
    'Traceroute_Demo',
    'traceroute_results'
  );
  if (!fs.existsSync(resultsDir)) {
    fs.mkdirSync(resultsDir, { recursive: true });
  }

  // 确保whisper-models目录存在
  const whisperModelsDir = path.join(isDev ? __dirname : process.resourcesPath, 'whisper-models');
  if (!fs.existsSync(whisperModelsDir)) {
    fs.mkdirSync(whisperModelsDir, { recursive: true });
    console.log(`创建Whisper模型目录: ${whisperModelsDir}`);
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

ipcMain.on('run-traceroute', (event, fullCommand) => {
  const globeWindow = new BrowserWindow({
    width: 1200,
    height: 900,
    title: `Cesium地球 - 的路由追踪`,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  globeWindow.loadFile(getResourcePath('globe_cesium.html'));
  globeWindow.webContents.openDevTools();

  const parts = fullCommand.split(' ');
  const command = parts[0].toLowerCase();
  const targetDomain = parts.length > 1 ? parts.slice(1).join(' ') : '';

  if (command !== 'traceroute' || !targetDomain) {
    event.sender.send('traceroute-output', '\n错误: 无效命令。请使用 "traceroute <域名/IP>"。\n');
    return;
  }
  event.sender.send('traceroute-output', `开始执行目标为 ${targetDomain} 的路由追踪...\n`);

  // 设置Python脚本路径
  const inputScriptPath = getResourcePath(path.join('Traceroute_Demo', 'InputFile.py'));
  const handlerScriptPath = getResourcePath(path.join('Traceroute_Demo', 'Handler.py'));
  const geolocateScriptPath = getResourcePath(path.join('Traceroute_Demo', 'ip_geolocate.py'));

  const inputProcess = spawnPythonProcess(
    inputScriptPath,
    [targetDomain],
    event,
    '[input]'
  );
  inputProcess.on('close', (handlerCode) => {
    event.sender.send('traceroute-output', `\n[input] 脚本执行完成，退出码: ${handlerCode}\n`);
    if (handlerCode === 0) {
      event.sender.send('traceroute-output', `input目录文件已生成，正在进行tracert...\n`);


      // 创建handler进程
      const handlerProcess = spawnPythonProcess(
        handlerScriptPath,
        [targetDomain],
        event,
        '[Handler]'
      );
      handlerProcess.on('close', (handlerCode) => {
        event.sender.send('traceroute-output', `\n[Handler] 脚本执行完成，退出码: ${handlerCode}\n`);

        if (handlerCode === 0) {
          event.sender.send('traceroute-output', `Traceroute数据已生成，正在为 ${targetDomain} 获取地理位置...\n`);

          // 创建地理位置处理进程
          const geolocateProcess = spawnPythonProcess(
            geolocateScriptPath,
            [targetDomain],
            event,
            '[地理位置]'
          );

          geolocateProcess.on('close', (geolocateCode) => {
            event.sender.send('traceroute-output', `\n[地理位置] 脚本执行完成，退出码: ${geolocateCode}\n`);

            if (geolocateCode === 0) {
              event.sender.send('traceroute-output', '地理位置数据处理完成，正在打开Cesium地球可视化...\n');

              // 创建Cesium窗口
              const globeWindow = new BrowserWindow({
                width: 1200,
                height: 900,
                title: `Cesium地球 - ${targetDomain}的路由追踪`,
                webPreferences: {
                  nodeIntegration: true,
                  contextIsolation: false,
                }
              });

              globeWindow.loadFile(getResourcePath('globe_cesium.html'));

              if (isDev) {
                globeWindow.webContents.openDevTools();
              }

            } else {
              event.sender.send('traceroute-output', '处理IP地理位置数据时出错。\n');
            }
          });
        } else {
          event.sender.send('traceroute-output', 'handler.py脚本执行出错（无法生成traceroute JSON）。\n');
        }
      });
    } else {
      event.sender.send('traceroute-output', 'input.py脚本执行出错。\n');
    }
  });
});

// 处理Whisper音频数据 - 使用whisper-node-addon重写
ipcMain.handle('process-whisper-audio', async (event, audioData, tempFileName) => {
  try {
    console.log(`开始处理音频数据，临时文件名: ${tempFileName}`);

    // 创建临时文件路径
    const audioFilePath = path.join(tempDir, tempFileName);
    console.log(`原始音频文件路径: ${audioFilePath}`);

    // 将ArrayBuffer写入文件
    fs.writeFileSync(audioFilePath, Buffer.from(audioData));
    console.log(`音频数据已写入文件，大小: ${audioData.length} 字节`);

    // 为转换后的文件创建路径 - 使用.wav扩展名
    const wavFilePath = path.join(tempDir, `converted_${Date.now()}.wav`);
    console.log(`转换后音频文件路径: ${wavFilePath}`);

    try {
      // 使用ffmpeg转换音频格式 - 确保是16kHz, 16bit, 单声道PCM格式
      const { execSync } = require('child_process');

      console.log('使用ffmpeg转换音频:');
      console.log(`ffmpeg路径: ${ffmpeg}`);

      // 构建并执行ffmpeg命令，指定所有关键参数
      const ffmpegCommand = `"${ffmpeg}" -y -loglevel info -i "${audioFilePath}" -acodec pcm_s16le -ar 16000 -ac 1 -f wav "${wavFilePath}"`;
      console.log(`执行命令: ${ffmpegCommand}`);

      const ffmpegOutput = execSync(ffmpegCommand, { encoding: 'utf8' });
      console.log('ffmpeg输出:', ffmpegOutput);

      // 验证转换后的文件
      if (!fs.existsSync(wavFilePath)) {
        throw new Error(`转换后的文件不存在: ${wavFilePath}`);
      }

      const outputStats = fs.statSync(wavFilePath);
      console.log(`转换成功: ${wavFilePath}, 大小: ${outputStats.size} 字节`);

      // 准备模型路径 - 使用项目中的模型文件
      const modelName = 'ggml-tiny.en.bin'; // 使用标准tiny模型名称
      const modelPath = path.join(getResourcePath('whisper-models'), modelName);
      console.log(`模型文件路径: ${modelPath}`);

      // 验证模型文件
      if (!fs.existsSync(modelPath)) {
        throw new Error(`模型文件不存在: ${modelPath}`);
      }

      const modelStats = fs.statSync(modelPath);
      console.log(`模型文件验证成功, 大小: ${modelStats.size} 字节`);

      // 检查文件大小是否合理，tiny模型应该约为75MB
      if (modelStats.size < 30000000) { // 小于30MB可能不完整
        console.warn(`警告: 模型文件大小异常(${modelStats.size} 字节)，可能不完整`);
      }

      // 执行转录
      console.log('开始执行Whisper转录...');

      const options = {
        model: modelPath,          // 模型文件路径
        fname_inp: wavFilePath,    // 输入音频文件路径
        language: 'en',            // 指定英语
        no_prints: false,          // 显示完整日志
        use_gpu: false,            // 不使用GPU
        translate: false,          // 不翻译
        no_timestamps: true,       // 不包含时间戳
        max_len: 0,                // 无长度限制
        audio_ctx: 0               // 默认音频上下文
      };

      console.log('转录参数:', JSON.stringify(options, null, 2));

      try {
        const result = await whisper.transcribe(options);
        console.log('转录完成, 原始结果:', result);

        // 清理临时文件
        try {
          fs.unlinkSync(audioFilePath);
          console.log(`临时文件已删除: ${audioFilePath}`);

          // 保留转换后的文件用于调试
          // fs.unlinkSync(wavFilePath);
          // console.log(`转换后的文件已删除: ${wavFilePath}`);
        } catch (cleanupError) {
          console.error('删除临时文件失败:', cleanupError);
        }

        // 处理各种可能的结果格式
        let textOutput = '';
        if (!result) {
          console.log('结果为空');
          return '未识别到内容';
        }

        // 处理不同类型的结果
        if (typeof result === 'string') {
          textOutput = result.trim();
          console.log('结果是字符串:', textOutput);
        } else if (typeof result === 'object') {
          if (result.text) {
            textOutput = result.text.trim();
            console.log('结果是对象.text:', textOutput);
          } else if (Array.isArray(result) && result.length > 0) {
            const firstItem = result[0];
            if (typeof firstItem === 'object' && firstItem.text) {
              textOutput = firstItem.text.trim();
              console.log('结果是数组对象:', textOutput);
            } else if (typeof firstItem === 'string') {
              textOutput = firstItem.trim();
              console.log('结果是字符串数组:', textOutput);
            } else if (Array.isArray(firstItem) && firstItem.length > 2) {
              // 处理形如 [["时间戳开始", "时间戳结束", "文本内容"]] 的格式
              textOutput = firstItem[2].trim();
              console.log('结果是时间戳数组:', textOutput);
            }
          } else {
            console.log('未知的对象结果格式:', JSON.stringify(result));
            // 如果无法解析，返回整个结果的JSON字符串，让前端处理
            return JSON.stringify(result);
          }
        } else {
          console.log(`未知结果类型: ${typeof result}`);
        }

        console.log('最终识别文本:', textOutput || '(无文本)');
        return textOutput || '未识别到内容';

      } catch (transcribeError) {
        console.error('转录过程错误:', transcribeError);
        throw transcribeError;
      }
    } catch (processingError) {
      console.error('音频处理或转录错误:', processingError);
      console.error('错误详情:', processingError.stack);
      throw processingError;
    }
  } catch (error) {
    console.error('整体处理失败:', error);
    console.error('错误堆栈:', error.stack);
    return `识别错误: ${error.message}`;
  }
});
