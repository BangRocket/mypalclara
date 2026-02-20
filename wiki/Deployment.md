# Deployment Guide

This guide covers deploying Clara in production environments.

## Deployment Options

| Option | Best For | Complexity |
|--------|----------|------------|
| Railway | Quick start, managed | Low |
| Docker Compose | Self-hosted, customizable | Medium |
| Manual | Full control | High |

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

### Custom Domain

1. Go to Settings > Domains
2. Add custom domain
3. Configure DNS CNAME record

## Docker Compose

### Basic Setup

```bash
# Clone repo
git clone https://github.com/BangRocket/mypalclara.git
cd mypalclara

# Configure
cp .env.example .env
# Edit .env with your values

# Run Discord bot only
docker-compose --profile discord up -d

# Run with PostgreSQL
docker-compose --profile discord --profile postgres up -d
```

### docker-compose.yml Profiles

| Profile | Services |
|---------|----------|
| `discord` | Discord bot |
| `postgres` | PostgreSQL + pgvector |
| `gateway` | Gateway server |
| `teams` | Teams adapter (beta) |

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

## Database Setup

### PostgreSQL with pgvector

```bash
# Create database
createdb clara_main
createdb clara_vectors

# Enable pgvector
psql clara_vectors -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Environment Variables

```bash
DATABASE_URL=postgresql://user:pass@host:5432/clara_main
MEM0_DATABASE_URL=postgresql://user:pass@host:5432/clara_vectors
```

### Migrations

Run migrations on first deploy:

```bash
poetry run python scripts/migrate.py
```

Or auto-migrate on startup (default behavior).

## Database Backups

### Backup Service

The `mypalclara/services/backup/` provides automated S3-compatible backups:

```bash
cd mypalclara/services/backup

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
- Shared MCP server configs
- Load balancer (future)

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
4. Review logs for errors

### Memory Not Working

1. Verify OPENAI_API_KEY is set
2. Check vector store connection
3. Review mem0 logs

### Database Issues

1. Check DATABASE_URL format
2. Verify pgvector extension
3. Run migrations

### MCP Servers Failing

1. Check server logs
2. Verify npm/node installed
3. Check OAuth tokens (hosted servers)

See [[Troubleshooting]] for more details.
