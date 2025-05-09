# Traceroute 

A Python-based, multi-protocol traceroute implementation and handler, with an accompanying Docker network of routers/servers for testing.

---

## Table of Contents

- [Overview](#overview)  
- [Features](#features)  
- [Prerequisites](#prerequisites)  
- [Getting Started](#getting-started)  
  - [Clone repository](#clone-repository)  
  - [Python environment setup](#python-environment-setup)  
  - [Run traceroute handler](#run-traceroute-handler)  
- [Docker Testbed](#docker-testbed)  
  - [Build images](#build-images)  
  - [Bring up network](#bring-up-network)  
  - [Run traceroute against containers](#run-traceroute-against-containers)  
- [Configuration](#configuration)  
- [Output & Results](#output--results)  
- [Contributing](#contributing)  
- [License](#license)  

---

## Overview

This project provides:

1. **`handler.py`** – A command-line handler that reads a list of targets (TXT/CSV), runs our custom `Traceroute` class over UDP/TCP/ICMP, and writes per-target JSON or text results.  
2. **`My_traceroute_fixed.py`** – Low-level traceroute engine that opens raw sockets, sends probes at increasing TTL, captures replies, and aggregates statistics.  
3. **Docker testbed** – A `docker-compose.yml` that brings up multiple router/server containers so you can test hops in a controlled environment.  
4. **Earth display** – An interactive globe visualization showing live ping paths and the relationships between IPs at each hop.

---

## Features

- Multi-protocol probing (UDP, TCP SYN, ICMP)  
- Per-hop RTT stats (min/avg/max/loss)  
- Extension support (e.g. MPLS labels)  
- Batch processing of target lists  
- JSON and human-readable text output  
- Interactive Earth globe visualization of ping routes and connected IPs  
- Docker-based virtual network for end-to-end testing  

---

## Prerequisites

- Python 3.7+  
- `pip` or `venv`  
- Linux or macOS (raw sockets require elevated privileges)  
- Docker & Docker Compose  

---

## Getting Started

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
sudo npm install
```
Note: Using sudo is required to ensure the application has the necessary permissions to run.












