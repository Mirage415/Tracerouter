// preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  runTraceroute: (cmd) => ipcRenderer.send('run-traceroute', cmd),
  onOutput: (fn) => ipcRenderer.on('traceroute-output', (_, data) => fn(data)),
  processWhisperAudio: (audioData, tempFileName) => ipcRenderer.invoke('process-whisper-audio', audioData, tempFileName),
  saveOptionJson: (content) => ipcRenderer.invoke('save-option-json', content)
});
// const { contextBridge, ipcRenderer } = require('electron');

