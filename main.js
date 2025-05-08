// main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const ffmpeg = require('ffmpeg-static');

// 尝试各种方式导入nodejs-whisper
let nodewhisper;
try {
  // 先尝试常规require
  const whisperModule = require('nodejs-whisper');
  console.log('Successfully imported nodejs-whisper, type:', typeof whisperModule);

  // 检查模块结构
  if (typeof whisperModule === 'function') {
    // 如果直接是函数，使用它
    nodewhisper = whisperModule;
    console.log('nodejs-whisper is a function, using directly');
  } else if (typeof whisperModule === 'object') {
    // 如果是对象，打印其所有键
    console.log('nodejs-whisper is an object with keys:', Object.keys(whisperModule));

    // 尝试找到可能的函数
    if (whisperModule.default && typeof whisperModule.default === 'function') {
      nodewhisper = whisperModule.default;
      console.log('Using whisperModule.default function');
    } else if (whisperModule.nodewhisper && typeof whisperModule.nodewhisper === 'function') {
      nodewhisper = whisperModule.nodewhisper;
      console.log('Using whisperModule.nodewhisper function');
    } else {
      // 如果没有合适的函数，直接存储整个模块
      nodewhisper = whisperModule;
      console.log('No suitable function found, storing the whole module');
    }
  } else {
    console.error('nodejs-whisper module is not a function or object:', typeof whisperModule);
    nodewhisper = null;
  }
} catch (error) {
  console.error('Error importing nodejs-whisper:', error);
  nodewhisper = null;
}

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
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

ipcMain.on('run-traceroute', (event, fullCommand) => {
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

// 处理Whisper音频数据
ipcMain.handle('process-whisper-audio', async (event, audioData, tempFileName) => {
  try {
    console.log(`开始处理音频数据，临时文件名: ${tempFileName}`);

    // 检查nodejs-whisper是否可用
    if (!nodewhisper) {
      throw new Error('nodejs-whisper模块未能正确加载，请重新安装该依赖');
    }

    // 打印nodewhisper对象结构以便调试
    console.log('nodewhisper类型:', typeof nodewhisper);

    // 创建临时文件路径
    const audioFilePath = path.join(tempDir, tempFileName);
    console.log(`音频文件路径: ${audioFilePath}`);

    // 将ArrayBuffer写入文件 - 使用wav格式，确保格式正确
    fs.writeFileSync(audioFilePath, Buffer.from(audioData));
    console.log(`音频数据已写入文件，大小: ${audioData.length} 字节`);

    // 检查ffmpeg是否存在并使用它进行转换
    try {
      const { execSync } = require('child_process');
      console.log('Using ffmpeg from ffmpeg-static at:', ffmpeg);

      // 尝试使用ffmpeg直接转换音频格式，确保格式兼容
      const wavFilePath = path.join(tempDir, `converted_${tempFileName}`);
      // 在命令中明确使用 ffmpeg-static 提供的路径，并确保路径中的空格被正确处理
      const ffmpegCommand = `"${ffmpeg}" -y -i "${audioFilePath}" -acodec pcm_s16le -ar 16000 -ac 1 "${wavFilePath}"`;
      console.log('Executing ffmpeg command:', ffmpegCommand);
      execSync(ffmpegCommand);
      console.log(`音频已转换为16kHz, 16bit, 单声道WAV格式: ${wavFilePath}`);

      // 使用转换后的文件
      const processFilePath = wavFilePath;

      // 检查模型目录
      const userDataPath = app.getPath('userData');
      const modelPath = path.join(userDataPath, 'whisper-models');
      if (!fs.existsSync(modelPath)) {
        fs.mkdirSync(modelPath, { recursive: true });
        console.log(`创建Whisper模型目录: ${modelPath}`);
      }

      // 添加更多调试信息
      console.log('尝试使用nodejs-whisper处理音频文件');
      console.log('音频文件是否存在:', fs.existsSync(processFilePath));
      console.log('音频文件大小:', fs.statSync(processFilePath).size);

      // 尝试不同的调用方法
      let result;
      if (typeof nodewhisper === 'function') {
        // 直接作为函数调用
        console.log('尝试直接调用nodewhisper函数');
        // 使用基本选项简化调用
        result = await nodewhisper(processFilePath, {
          modelName: 'tiny.en',
          autoDownloadModelName: 'tiny.en',
          modelDir: modelPath,
          removeWavFileAfterTranscription: false,
          whisperOptions: {
            language: 'auto',
            outputInText: true,
            temperature: 0,
          }
        });
      } else if (nodewhisper.nodewhisper && typeof nodewhisper.nodewhisper === 'function') {
        // 使用导出的nodewhisper函数
        console.log('尝试调用nodewhisper.nodewhisper函数');
        result = await nodewhisper.nodewhisper(processFilePath, {
          modelName: 'tiny.en',
          autoDownloadModelName: 'tiny.en',
          modelDir: modelPath,
          whisperOptions: {
            language: 'auto',
            outputInText: true,
            temperature: 0,
          }
        });
      } else if (nodewhisper.default && typeof nodewhisper.default === 'function') {
        // 使用默认导出
        console.log('尝试调用nodewhisper.default函数');
        result = await nodewhisper.default(processFilePath, {
          modelName: 'tiny.en',
          autoDownloadModelName: 'tiny.en',
          modelDir: modelPath,
          whisperOptions: {
            language: 'auto',
            outputInText: true,
            temperature: 0,
          }
        });
      } else {
        // 没有可用的函数
        throw new Error('无法找到可用的whisper函数调用方法，请检查nodejs-whisper模块');
      }

      console.log('Whisper处理完成, 结果:', result);

      // 清理临时文件
      try {
        fs.unlinkSync(audioFilePath);
        fs.unlinkSync(wavFilePath);
        console.log('临时音频文件已删除');
      } catch (cleanupError) {
        console.error('删除临时文件失败:', cleanupError.message);
      }

      // 返回识别结果
      let textOutput = typeof result === 'object' ? result.text || '' : result || '';

      // 使用正则表达式移除时间戳，例如 [00:00:00.000 --> 00:00:01.160]
      // 这个正则表达式会匹配方括号内的任意字符，直到遇到 " --> "，然后再匹配方括号内的任意字符
      // \s* 用来匹配时间戳后面可能存在的空格
      textOutput = textOutput.replace(/\[\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}\]\s*/g, '');

      // 移除可能残留的单独的时间戳，例如 [00:00:00.000]
      textOutput = textOutput.replace(/\[\d{2}:\d{2}:\d{2}\.\d{3}\]\s*/g, '');

      // 进一步清理，移除纯数字和特定标点组合，防止残留的类似时间戳的片段
      // 例如，移除像 "00:00:00.000" 这样的模式，如果它独立存在
      textOutput = textOutput.replace(/\b\d{2}:\d{2}:\d{2}\.\d{3}\b\s*/g, '');

      // 确保移除文本前后的多余空格
      textOutput = textOutput.trim();

      console.log('移除时间戳后的文本:', textOutput);
      return textOutput || '未识别到内容'; // 确保即使清理后为空，也有默认值
    } catch (processingError) {
      console.error('音频处理错误:', processingError.message);
      throw processingError; // 继续向上抛出以便外层catch捕获
    }
  } catch (error) {
    console.error('Whisper处理失败:', error);
    console.error('错误堆栈:', error.stack);

    // 返回错误信息
    return `识别错误: ${error.message}`;
  }
});
