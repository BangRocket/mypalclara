# Sandbox System

Secure code execution environment for Clara.

## Overview

The sandbox system provides:
- Isolated code execution
- Multiple backend options (Docker, Incus, Remote)
- Per-user containers
- Resource limits (CPU, memory, time)
- File operations within sandbox

## Backend Comparison

| Feature | Docker | Incus Container | Incus VM | Remote |
|---------|--------|-----------------|----------|--------|
| Startup time | ~1s | ~2s | ~10s | Network |
| Isolation | Namespace | Namespace + user ns | Full hardware | Full |
| Memory overhead | Low | Low | ~100-300MB | None |
| Untrusted code | Moderate | Moderate | High | High |
| Local install | Required | Required | Required | No |

## Configuration

### Mode Selection

```bash
SANDBOX_MODE=auto    # auto, docker, incus, incus-vm, remote
```

- `auto` - Use remote if configured, fall back to local
- `docker` - Docker containers
- `incus` - Incus containers (faster, lighter)
- `incus-vm` - Incus VMs (stronger isolation)
- `remote` - Remote sandbox API

### Docker Backend

```bash
SANDBOX_MODE=docker
DOCKER_SANDBOX_IMAGE=python:3.12-slim
DOCKER_SANDBOX_TIMEOUT=900          # Idle timeout (seconds)
DOCKER_SANDBOX_MEMORY=512m          # Memory limit
DOCKER_SANDBOX_CPU=1.0              # CPU limit
```

### Incus Backend

```bash
SANDBOX_MODE=incus
INCUS_SANDBOX_IMAGE=images:debian/12/cloud
INCUS_SANDBOX_TYPE=container        # container or vm
INCUS_SANDBOX_TIMEOUT=900
INCUS_SANDBOX_MEMORY=512MiB
INCUS_SANDBOX_CPU=1
INCUS_REMOTE=local
```

### Remote Backend

```bash
SANDBOX_MODE=remote
SANDBOX_API_URL=https://sandbox.example.com
SANDBOX_API_KEY=your-api-key
SANDBOX_TIMEOUT=60                  # Request timeout
```

## Docker Setup

### Prerequisites

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Verify
docker --version
docker run hello-world
```

### Image Customization

Create custom Dockerfile for additional packages:

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    numpy \
    pandas \
    requests
```

Build and use:

```bash
docker build -t clara-sandbox .
DOCKER_SANDBOX_IMAGE=clara-sandbox
```

## Incus Setup

### Installation

```bash
# Ubuntu/Debian
sudo apt install incus

# Initialize
sudo incus admin init

# Add user to incus-admin group
sudo usermod -aG incus-admin $USER
```

### Container vs VM

**Containers** (`INCUS_SANDBOX_TYPE=container`):
- Shared kernel with host
- Fast startup (~2s)
- Lower overhead
- Good for trusted code

**VMs** (`INCUS_SANDBOX_TYPE=vm`):
- Full virtualization
- Slower startup (~10s)
- Higher overhead
- Better for untrusted code

### Custom Images

```bash
# List available images
incus image list images:

# Launch custom container
incus launch images:ubuntu/22.04 test-sandbox
incus exec test-sandbox -- apt install python3 pip
incus publish test-sandbox --alias clara-sandbox
incus delete test-sandbox

# Use custom image
INCUS_SANDBOX_IMAGE=clara-sandbox
```

## Remote Sandbox Service

### Self-Hosted Deployment

The remote sandbox service is in `sandbox_service/`:

```bash
cd sandbox_service
docker-compose build sandbox-image
docker-compose up -d
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sandbox/{user_id}/create` | POST | Create sandbox |
| `/sandbox/{user_id}/execute` | POST | Run Python code |
| `/sandbox/{user_id}/shell` | POST | Run shell command |
| `/sandbox/{user_id}/file` | GET/POST/DELETE | File operations |
| `/sandbox/{user_id}/pip/install` | POST | Install package |
| `/sandbox/{user_id}/destroy` | DELETE | Remove sandbox |
| `/health` | GET | Health check |

### Configuration

```bash
# API settings
SANDBOX_API_KEY=your-secret-key
SANDBOX_API_HOST=0.0.0.0
SANDBOX_API_PORT=8080

# Container settings
SANDBOX_DOCKER_IMAGE=python:3.12-slim
SANDBOX_DOCKER_TIMEOUT=900
SANDBOX_DOCKER_MEMORY=512m
SANDBOX_DOCKER_CPU=1.0
SANDBOX_MAX_CONTAINERS=10
SANDBOX_DATA_DIR=/data/sandboxes
```

### Docker Compose

```yaml
version: '3.8'

services:
  sandbox-api:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - sandbox-data:/data
    environment:
      - SANDBOX_API_KEY
      - SANDBOX_DOCKER_IMAGE
      - SANDBOX_MAX_CONTAINERS

  caddy:
    image: caddy:2
    ports:
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile

volumes:
  sandbox-data:
```

## Usage in Clara

### Execute Python

```
@Clara run this Python code:
```python
import math
print(math.pi)
```
```

### Shell Commands

```
@Clara run: ls -la
```

### Install Packages

```
@Clara install numpy and pandas in the sandbox
```

### File Operations

```
@Clara save this to sandbox: output.txt
@Clara list files in sandbox
@Clara read sandbox file: output.txt
```

## Security

### Resource Limits

| Resource | Default | Config |
|----------|---------|--------|
| Memory | 512MB | `*_SANDBOX_MEMORY` |
| CPU | 1 core | `*_SANDBOX_CPU` |
| Timeout | 900s | `*_SANDBOX_TIMEOUT` |
| Disk | Unlimited | Container volume |

### Network Isolation

Sandboxes have limited network access:
- Docker: Can configure network mode
- Incus: Network policies
- Remote: Isolated by design

### Filesystem Isolation

Each user gets isolated filesystem:
- Docker: Separate containers
- Incus: Separate instances
- Remote: User-scoped directories

## Troubleshooting

### Docker Not Available

```
Error: Docker daemon not running
```

**Solution:**
```bash
sudo systemctl start docker  # Linux
open -a Docker               # macOS
```

### Incus Permission Denied

```
Error: Permission denied
```

**Solution:**
```bash
sudo usermod -aG incus-admin $USER
newgrp incus-admin
```

### Container Timeout

```
Error: Execution timed out
```

**Solution:**
- Increase timeout: `DOCKER_SANDBOX_TIMEOUT=1800`
- Optimize code
- Use remote for long tasks

### Memory Limit Exceeded

```
Error: OOM killed
```

**Solution:**
- Increase limit: `DOCKER_SANDBOX_MEMORY=1g`
- Optimize memory usage
- Process data in chunks

## Architecture

```
┌─────────────────┐
│    Clara        │
│  (tool call)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Sandbox Manager │  (sandbox/manager.py)
│  Auto-selector  │
└────────┬────────┘
         │
    ┌────┼────┬────────┐
    ▼    ▼    ▼        ▼
┌──────┐┌──────┐┌──────┐┌──────┐
│Docker││Incus ││Incus ││Remote│
│      ││ Cont ││  VM  ││      │
└──────┘└──────┘└──────┘└──────┘
```

## See Also

- [[Configuration]] - All sandbox configuration
- [[Tool-Development]] - Creating tools that use sandbox
- [[Deployment]] - Production deployment
