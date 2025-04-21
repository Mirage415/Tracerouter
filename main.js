// main.js
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

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
  win.webContents.openDevTools();
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// 接收识别到的命令，调用 Python traceroute
ipcMain.on('run-traceroute', (event, fullCommand) => {
  // fullCommand e.g. "traceroute google.com"
  const args = fullCommand.split(' ').slice(1); // ['google.com']
  const py = spawn('python3', [
    path.join(__dirname, 'python', 'My_Traceroute.py'),
    ...args
  ]);

  py.stdout.on('data', data => {
    event.sender.send('traceroute-output', data.toString());
  });
  py.stderr.on('data', data => {
    event.sender.send('traceroute-output', data.toString());
  });
  py.on('close', code => {
    event.sender.send('traceroute-output', `\nProcess exited with code ${code}`);
  });
});
