# Tracerouter 

An Electron-based, multi-protocol traceroute visualization application with an interactive globe display for network path tracking.

---

## Table of Contents

- [Overview](#overview)  
- [Features](#features)  
- [Prerequisites](#prerequisites)  
- [Getting Started](#getting-started)  
  - [Direct Download](#direct-download)  
  - [Build from Source](#build-from-source)  
- [Mac-Specific Configuration](#mac-specific-configuration)  
  - [Microphone Permissions](#microphone-permissions)  
  - [Network Permissions](#network-permissions)  
- [Usage](#usage)  
- [Voice Commands](#voice-commands)  
- [Troubleshooting](#troubleshooting)  
- [Uninstallation](#uninstallation)  
- [Technical Support](#technical-support)  

---

## Overview

Tracerouter is an Electron-based route tracing visualization application that tracks the complete path of network packets from source to destination and displays them visually on an interactive globe.

---

## Features

- Multi-protocol probing (UDP, TCP SYN, ICMP)  
- Per-hop RTT statistics (min/avg/max/loss rate)  
- Extension support (e.g., MPLS labels)  
- Batch processing of target lists  
- JSON and human-readable text output  
- Interactive globe visualization of ping routes and connected IPs  
- Voice command control functionality  

---

## Prerequisites

- macOS 14.0 or higher  
- Network connection  
- Microphone (for voice functionality)  

---

## Getting Started

<<<<<<< HEAD

### Build from Source

1. Ensure you have Node.js (v16 or higher recommended) and npm installed

```bash
# Clone the repository
git clone https://github.com/Mirage415/Tracerouter.git
cd tracerouter

# Install dependencies
npm install

# Run development version
npm start

# Build the application
npm run build
```

---

## Mac-Specific Configuration

### Microphone Permissions

1. The system will request microphone access permission when you first run the application
2. If you declined permission, you can enable it by:
   - Opening "System Preferences" > "Security & Privacy" > "Privacy" > "Microphone"
   - Checking the Tracerouter application

### Network Permissions

1. Network access permissions are required to use the traceroute functionality
2. If you see a firewall warning, please allow the application to access the network

---

## Usage

1. After opening the application, an interactive globe interface will be displayed
2. Enter a target IP or domain name in the input field, or use voice commands
3. Click the "Start Tracing" button or say "Start tracing" to initiate route tracing
4. Results will be displayed in real-time on the globe and in the panel below for detailed information

---

## Voice Commands

- "Start tracing" - Begin route tracing
- "Trace [target]" - Trace the specified target (e.g., "Trace google.com")
- "Stop" - Stop the current trace
- "Clear" - Clear display results

---

## Troubleshooting

### Voice Recognition Not Working

Make sure you have granted microphone access permissions and that the system volume is turned on.

### macOS Voice Recognition Library Issues

If you encounter issues with the whisper voice recognition library on macOS, you may need to fix the dynamic library paths using the following commands:

```bash
# Fix the libwhisper dynamic library ID
install_name_tool \
  -id @rpath/libwhisper.1.dylib \
  node_modules/whisper-node-addon/platform/darwin-x64/libwhisper.1.dylib

# Add the relative loader path to the whisper.node module
install_name_tool \
  -add_rpath "@loader_path" \
  node_modules/whisper-node-addon/platform/darwin-x64/whisper.node
```

**Important Note**: The `darwin-x64` part of the path should be adjusted based on your Mac's architecture:
- Use `darwin-x64` for Intel-based Macs
- Use `darwin-arm64` for Apple Silicon Macs (M1/M2/M3)

You can check your architecture by running `uname -m` in the terminal:
- `x86_64` means Intel (use darwin-x64)
- `arm64` means Apple Silicon (use darwin-arm64)

### Application Won't Start

1. Check if you're running from the Applications folder
2. Try right-clicking the application > "Open" to bypass macOS security restrictions

### Tracing Fails

Some networks may block traceroute packets. Try switching protocols (UDP/TCP/ICMP) or check your network connection.

---

## Uninstallation

Drag the application from the Applications folder to the Trash, or use a third-party uninstallation tool to thoroughly clean application data.

---

## Technical Support

If you encounter any issues, please submit an issue through the GitHub repository or send an email to support@example.com.
=======
### Clone repository
Clone the Tracerouter repository to your local machine using the following command:
```bash
git clone https://github.com/your-username/Tracerouter.git
cd Tracerouter
```
Note: If you encounter any issues with cloning the repository, such as a failed connection, please ensure the URL is correct and your network connection is stable. You may need to retry the command.

### If you have downloaded the Tracerouter
If you have already downloaded the Tracerouter repository, navigate to the directory where it is located:
```bash
cd your_filepath/Tracerouter
```
Replace /path/to/Tracerouter with the actual path to the directory where you have downloaded the project.

### install the dependencies
racerouter requires some dependencies to run. Install them using npm:
```bash
npm install
```

### Run the Application
Start the Tracerouter application using the following command:
```bash
sudo npm start
```
Note: Using sudo is required to ensure the application has the necessary permissions to run.












>>>>>>> ac21b1176ef4819eab1402fa8597567e01eea12c
