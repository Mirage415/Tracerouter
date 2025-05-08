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

```bash
git clone https://github.com/your-org/traceroute-demo.git
cd traceroute-demo