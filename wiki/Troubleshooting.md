# Troubleshooting

Common issues and solutions for MyPalClara.

## Installation Issues

### Poetry Not Found

**Symptom:** `poetry: command not found`

**Solution:**
```bash
# Add Poetry to PATH
export PATH="$HOME/.local/bin:$PATH"

# Add to shell profile for persistence
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Python Version Mismatch

**Symptom:** `Python 3.11+ required` or import errors

**Solution:**
```bash
# Check Python version
python3 --version

# Install Python 3.12 via pyenv
pyenv install 3.12
pyenv global 3.12

# Reinstall dependencies
poetry env remove python
poetry install
```

### Import Errors

**Symptom:** `ModuleNotFoundError` when running the bot

**Solution:**
```bash
# Ensure you're in the project directory
cd mypalclara

# Activate virtual environment
poetry shell

# Or run directly with poetry
poetry run python -m mypalclara.adapters.discord
```

## Discord Bot Issues

### Bot Not Responding

**Checklist:**
1. Verify token is correct in `.env`
2. Check intents are enabled in Discord Developer Portal:
   - Message Content Intent
   - Server Members Intent
   - Presence Intent
3. Verify bot has channel permissions
4. Check channel mode: `/clara status`

**Debug:**
```bash
# Check logs
poetry run python -m mypalclara.adapters.discord 2>&1 | tee bot.log

# Daemon mode logs
poetry run python -m mypalclara.adapters.discord --status
tail -f /var/log/clara.log
```

### Bot Offline in Discord

**Causes:**
- Invalid token
- Network issues
- Rate limiting

**Solution:**
```bash
# Regenerate token in Discord Developer Portal
# Update DISCORD_BOT_TOKEN in .env
# Restart bot

poetry run python -m mypalclara.adapters.discord --stop
poetry run python -m mypalclara.adapters.discord --daemon
```

### Permission Errors

**Symptom:** Bot can't send messages or reactions

**Solution:**
1. Check bot role position (must be above managed roles)
2. Verify channel-specific permissions
3. Required permissions:
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Add Reactions

### Channel Mode Issues

**Symptom:** Bot responds when it shouldn't (or vice versa)

**Check mode:**
```
/clara status
```

**Reset mode:**
```
/clara mode mention
```

## Memory System Issues

### mem0 Initialization Errors

**Symptom:** `Error initializing mem0` or embedding errors

**Checklist:**
1. Verify `OPENAI_API_KEY` is set (required for embeddings)
2. Check API key has embedding permissions
3. Verify vector store is accessible

**Debug:**
```python
# Test embeddings
import openai
client = openai.OpenAI()
response = client.embeddings.create(
    model="text-embedding-3-small",
    input="test"
)
print(response.data[0].embedding[:5])
```

### Qdrant Connection Issues (Development)

**Symptom:** `Connection refused` to Qdrant

**Solution:**
Qdrant runs embedded by default. If errors persist:
```bash
# Check qdrant_data directory permissions
ls -la qdrant_data/

# Clear and restart
rm -rf qdrant_data/
poetry run python -m mypalclara.adapters.discord
```

### pgvector Issues (Production)

**Symptom:** `extension "vector" does not exist`

**Solution:**
```sql
-- Connect to database
psql $MEM0_DATABASE_URL

-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Graph Memory Errors

**Symptom:** FalkorDB connection errors

**Solution:**
```bash
# Disable graph memory if not needed
ENABLE_GRAPH_MEMORY=false

# Or fix FalkorDB connection
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_PASSWORD=your-password
FALKORDB_GRAPH_NAME=clara
```

## Database Issues

### SQLite Lock Errors

**Symptom:** `database is locked`

**Solution:**
```bash
# Check for multiple processes
ps aux | grep discord_bot

# Stop daemon
poetry run python -m mypalclara.adapters.discord --stop

# Clear lock
rm -f assistant.db-journal
```

### PostgreSQL Connection Errors

**Symptom:** `could not connect to server`

**Checklist:**
1. Verify `DATABASE_URL` format: `postgresql://user:pass@host:5432/dbname`
2. Check network connectivity
3. Verify credentials

**Debug:**
```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check SSL requirements
# Some hosts require sslmode=require
DATABASE_URL="postgresql://user:pass@host:5432/dbname?sslmode=require"
```

### Migration Errors

**Symptom:** Table doesn't exist or schema mismatch

**Solution:**
```bash
# Check migration status
poetry run python scripts/migrate.py status

# Run pending migrations
poetry run python scripts/migrate.py

# If corrupted, reset (DANGEROUS)
poetry run python scripts/migrate.py reset
```

## LLM Provider Issues

### API Key Errors

**Symptom:** `401 Unauthorized` or `Invalid API key`

**Checklist by provider:**

**OpenRouter:**
```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

**Anthropic:**
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

**OpenAI:**
```bash
OPENAI_API_KEY=sk-...
```

### Rate Limiting

**Symptom:** `429 Too Many Requests`

**Solutions:**
1. Implement backoff (automatic in most cases)
2. Upgrade API tier
3. Use lower tier models for simple tasks

### Model Not Found

**Symptom:** `Model not found` or `Invalid model`

**Solution:**
Check model availability for your provider:
```bash
# OpenRouter
OPENROUTER_MODEL=anthropic/claude-sonnet-4

# Anthropic
ANTHROPIC_MODEL=claude-sonnet-4-5

# OpenAI
CUSTOM_OPENAI_MODEL=gpt-4o
```

## MCP Server Issues

### Server Won't Start

**Symptom:** MCP server shows "failed" status

**Debug:**
```
/mcp status <server-name>
```

**Common fixes:**
1. Check Node.js installed: `node --version`
2. Verify npm packages: `npm list -g`
3. Check server logs in `.mcp_servers/`

### OAuth Authentication Failed

**Symptom:** "pending_auth" status persists

**Solution:**
```
# Start fresh OAuth flow
/mcp oauth start <server>

# Visit the URL and authorize
# Complete with code
/mcp oauth complete <server> <code>
```

### Tool Not Found

**Symptom:** `Tool not found: server__tool`

**Checklist:**
1. Server is enabled: `/mcp list`
2. Server is connected: `/mcp status <server>`
3. Tool exists: `/mcp tools <server>`

## Sandbox Issues

### Docker Not Available

**Symptom:** `Docker daemon not running`

**Solution:**
```bash
# Start Docker
sudo systemctl start docker  # Linux
open -a Docker               # macOS

# Verify
docker ps
```

### Code Execution Timeout

**Symptom:** `Execution timed out`

**Solutions:**
1. Increase timeout:
   ```bash
   DOCKER_SANDBOX_TIMEOUT=1800  # 30 minutes
   ```
2. Optimize code
3. Break long-running tasks into smaller chunks

### Permission Denied in Sandbox

**Symptom:** `Permission denied` writing files

**Solution:**
Files in sandbox are ephemeral. Use local storage:
```
save_to_local(filename="output.txt", content="...")
```

## Gateway Issues

### Connection Refused

**Symptom:** Adapter can't connect to gateway

**Checklist:**
1. Gateway is running: `poetry run python -m mypalclara.gateway`
2. Check host/port match:
   ```bash
   CLARA_GATEWAY_HOST=127.0.0.1
   CLARA_GATEWAY_PORT=18789
   ```
3. Firewall allows connection

### Hook Execution Failed

**Symptom:** Hook errors in logs

**Debug:**
```bash
# Check hooks.yaml syntax
cat hooks/hooks.yaml

# Test command manually
echo "test" | bash -c "your-command"
```

## Performance Issues

### Slow Responses

**Possible causes:**
1. Large context window - reduce `DISCORD_MAX_MESSAGES`
2. Many MCP servers - disable unused ones
3. Graph memory enabled - disable if not needed
4. Model tier - use lower tier for simple queries

### High Memory Usage

**Solutions:**
1. Limit conversation history
2. Reduce `DISCORD_CHANNEL_HISTORY_LIMIT`
3. Clear old sessions: `poetry run python scripts/clear_dbs.py`

## Getting Help

### Logs

```bash
# Discord bot logs
poetry run python -m mypalclara.adapters.discord 2>&1 | tee debug.log

# Gateway logs
poetry run python -m mypalclara.gateway 2>&1 | tee gateway.log

# With timestamps
poetry run python -m mypalclara.adapters.discord 2>&1 | ts '[%Y-%m-%d %H:%M:%S]' | tee debug.log
```

### Debug Mode

Set environment variable for verbose output:
```bash
DEBUG=1 poetry run python -m mypalclara.adapters.discord
```

### Report Issues

1. Check existing issues: https://github.com/BangRocket/mypalclara/issues
2. Include:
   - Error message
   - Steps to reproduce
   - Environment (OS, Python version)
   - Relevant config (redact secrets)

