# Clara Sandbox Service

A self-hosted sandbox API for secure, persistent code execution via Docker containers.

## Quick Start

### 1. Build the sandbox container image

```bash
docker-compose build sandbox-image
```

### 2. Set environment variables

```bash
export SANDBOX_API_KEY="your-secure-api-key"
export SANDBOX_DOMAIN="sandbox.yourdomain.com"  # For production
```

### 3. Start the service

**Development (no HTTPS):**
```bash
docker-compose up -d sandbox-api
```

**Production (with Caddy/HTTPS):**
```bash
docker-compose --profile production up -d
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (no auth) |
| GET | `/info` | Service info |
| POST | `/sandbox/{user_id}/create` | Create sandbox |
| GET | `/sandbox/{user_id}/status` | Get status |
| POST | `/sandbox/{user_id}/stop` | Stop sandbox |
| POST | `/sandbox/{user_id}/restart` | Restart sandbox |
| DELETE | `/sandbox/{user_id}` | Delete sandbox |
| POST | `/sandbox/{user_id}/execute` | Run Python code |
| POST | `/sandbox/{user_id}/shell` | Run shell command |
| POST | `/sandbox/{user_id}/pip/install` | Install package |
| GET | `/sandbox/{user_id}/pip/list` | List packages |
| GET | `/sandbox/{user_id}/files` | List files |
| GET | `/sandbox/{user_id}/file` | Read file |
| POST | `/sandbox/{user_id}/file` | Write file |
| DELETE | `/sandbox/{user_id}/file` | Delete file |
| POST | `/sandbox/{user_id}/unzip` | Extract archive |

## Authentication

All endpoints except `/health` require the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" https://sandbox.example.com/info
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SANDBOX_API_KEY` | (required) | API authentication key |
| `SANDBOX_API_HOST` | `0.0.0.0` | API bind address |
| `SANDBOX_API_PORT` | `8080` | API port |
| `SANDBOX_DOCKER_IMAGE` | `clara-sandbox:latest` | Sandbox container image |
| `SANDBOX_DOCKER_TIMEOUT` | `900` | Idle container timeout (seconds) |
| `SANDBOX_DOCKER_MEMORY` | `512m` | Memory limit per container |
| `SANDBOX_DOCKER_CPU` | `1.0` | CPU limit per container |
| `SANDBOX_DATA_DIR` | `/data/sandboxes` | Persistent storage path |
| `SANDBOX_MAX_CONTAINERS` | `50` | Maximum concurrent containers |
| `SANDBOX_DOMAIN` | `localhost` | Domain for Caddy HTTPS |

## VPS Setup

1. Install Docker
2. Clone this directory to the VPS
3. Build the sandbox image
4. Configure environment variables
5. Start with docker-compose

See the main project's technical specification for detailed VPS setup instructions.
