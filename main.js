// main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// 处理路径，确保在打包和开发环境中都能正常工作
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

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
      contextIsolation: true
    }
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
  const handlerScriptPath = getResourcePath(path.join('python', 'handler.py'));
  const geolocateScriptPath = getResourcePath(path.join('Traceroute_Demo', 'ip_geolocate.py'));

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
});
