// preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  runTraceroute: (cmd) => ipcRenderer.send('run-traceroute', cmd),
  onOutput: (fn) => ipcRenderer.on('traceroute-output', (_, data) => fn(data))
});