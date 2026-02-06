# Deployment Guide

This guide covers deploying Clara in production environments.

## Deployment Options

| Option | Best For | Complexity |
|--------|----------|------------|
| Docker Compose | Self-hosted, customizable | Low-Medium |
| Railway | Quick start, managed | Low |
| Manual | Full control | High |

## Docker Compose

### Basic Setup

```bash
# Clone repo
git clone https://github.com/BangRocket/mypalclara.git
cd mypalclara

# Configure
cp .env.docker.example .env
# Edit .env with your values

# Run Discord bot with databases
docker-compose --profile discord up -d

# Run gateway with adapters
docker-compose --profile gateway --profile adapters up -d
```

### Docker Compose Profiles

| Profile | Services |
|---------|----------|
| `discord` | Discord bot (standalone mode) |
| `gateway` | Gateway server |
| `adapters` | Gateway-connected Discord adapter |
| `teams` | Teams adapter |
| `qdrant` | Qdrant vector database |
| `redis` | Redis cache |

**Always-on services** (no profile needed):
- `postgres` - Main PostgreSQL database (port 5442)
- `postgres-vectors` - pgvector database (port 5443)
- `falkordb` - FalkorDB graph database (port 6380)

### Custom Build

```yaml
services:
  clara:
    build: .
    env_file: .env
    volumes:
      - ./clara_files:/app/clara_files
      - ./mcp_servers:/app/mcp_servers
    restart: unless-stopped
```

## Railway Deployment

### Quick Start

1. Fork the repository
2. Connect to [Railway](https://railway.app)
3. Create new project from GitHub repo
4. Add environment variables
5. Deploy

### Environment Variables

Set these in Railway dashboard:

```bash
# Required
DISCORD_BOT_TOKEN=your-token
OPENAI_API_KEY=your-key
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key

# Database (auto-provisioned by Railway)
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

### Postgres Add-on

Railway can provision PostgreSQL:
1. Add PostgreSQL plugin
2. Database URL auto-configured
3. Enable pgvector extension in SQL console:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

## Database Setup

### PostgreSQL with pgvector

```bash
# Create databases
createdb clara_main
createdb clara_vectors

# Enable pgvector
psql clara_vectors -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@host:5432/clara_main
ROOK_DATABASE_URL=postgresql://user:pass@host:5432/clara_vectors
```

### Migrations

Run migrations on first deploy:

```bash
poetry run python scripts/migrate.py
```

Check migration status:

```bash
poetry run python scripts/migrate.py status
```

## Database Backups

### Backup Service

The `backup_service/` provides automated S3-compatible backups:

```bash
cd backup_service

# Configure
export S3_BUCKET=clara-backups
export S3_ENDPOINT_URL=https://s3.wasabisys.com
export S3_ACCESS_KEY=your-key
export S3_SECRET_KEY=your-secret

# Run backup
python backup.py

# List backups
python backup.py --list
```

### Scheduled Backups

Deploy as a cron job or Railway scheduled task:

```yaml
# Railway cron schedule
cron: "0 3 * * *"  # 3 AM daily
```

### Restore

```bash
# Download backup
aws s3 cp s3://clara-backups/backups/clara/clara_YYYYMMDD.sql.gz . \
  --endpoint-url=https://s3.wasabisys.com

# Decompress and restore
gunzip clara_YYYYMMDD.sql.gz
psql $DATABASE_URL < clara_YYYYMMDD.sql
```

## Scaling

### Single Instance

Suitable for personal use:
- SQLite database
- Qdrant for vectors
- Local MCP servers

### Production (Multi-Instance)

For team or public use:
- PostgreSQL for sessions
- pgvector for memory
- FalkorDB for graph relations
- Shared MCP server configs

### Resource Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Memory | 512MB | 2GB |
| CPU | 1 core | 2 cores |
| Storage | 1GB | 10GB |
| Postgres | 256MB | 1GB |

## Monitoring

### Discord Monitor Dashboard

```bash
DISCORD_MONITOR_ENABLED=true
DISCORD_MONITOR_PORT=8001
```

Access at `http://your-host:8001`

### Console Log Mirroring

Mirror logs to Discord channel:

```bash
DISCORD_LOG_CHANNEL_ID=123456789
```

### Health Checks

Gateway health endpoint:
```bash
curl http://localhost:18789/health
```

## Security

### Environment Variables

- Never commit `.env` to git
- Use secrets management in production
- Rotate API keys periodically

### Network

- Use HTTPS for public endpoints
- Restrict gateway to internal network
- Configure firewall rules

### Discord

- Restrict to allowed servers
- Use role-based access
- Monitor admin operations

## Troubleshooting

### Bot Not Responding

1. Check Discord bot token
2. Verify bot is in the server
3. Check channel permissions
4. Review logs: `poetry run python -m mypalclara.gateway logs`

### Memory Not Working

1. Verify OPENAI_API_KEY is set
2. Check vector store connection
3. Review Rook configuration in `config/rook.py`

### Database Issues

1. Check DATABASE_URL format
2. Verify pgvector extension
3. Run migrations: `poetry run python scripts/migrate.py`

### MCP Servers Failing

1. Check server logs
2. Verify npm/node installed
3. Check OAuth tokens (hosted servers)

See [[Troubleshooting]] for more details.
