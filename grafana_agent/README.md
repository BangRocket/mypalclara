# Grafana Agent for Clara Metrics

Scrapes Prometheus metrics from the Discord bot and pushes to Grafana Cloud.

## Setup

### 1. Get Grafana Cloud Credentials

1. Go to [Grafana Cloud](https://grafana.com/products/cloud/) and sign in
2. Navigate to **Connections** → **Add new connection** → **Hosted Prometheus metrics**
3. Note your:
   - **Remote Write URL**: `https://prometheus-prod-XX-prod-XX.grafana.net/api/prom/push`
   - **Username**: Your Grafana Cloud stack user ID (a number)
   - **Password**: Generate an API key with `MetricsPublisher` role

### 2. Deploy to Railway

1. Create a new service in Railway from this directory
2. Set root directory to `grafana_agent`
3. Set environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `GRAFANA_REMOTE_WRITE_URL` | Prometheus remote write endpoint | `https://prometheus-prod-10-prod-us-central-0.grafana.net/api/prom/push` |
| `GRAFANA_CLOUD_USER` | Your Grafana Cloud user ID | `123456` |
| `GRAFANA_CLOUD_API_KEY` | API key with MetricsPublisher role | `glc_xxx...` |
| `METRICS_TARGET` | Discord bot metrics endpoint (optional) | `discord.railway.internal:9090` |

### 3. Verify

1. Check Railway logs for successful scrapes
2. In Grafana Cloud, go to **Explore** → select your Prometheus datasource
3. Query for `cortex_` or `clara_` metrics

## Metrics Available

### Cortex Memory System
- `cortex_memories_stored_total` - Memories stored by type
- `cortex_memories_retrieved_total` - Memories retrieved
- `cortex_retrieval_latency_seconds` - Semantic search latency
- `cortex_store_latency_seconds` - Memory store latency
- `cortex_working_memory_size` - Working memory count per user
- `cortex_redis_connected` / `cortex_postgres_connected` - Connection status
- `cortex_cache_hits_total` / `cortex_cache_misses_total` - Cache performance

### Clara Bot
- `clara_messages_processed_total` - Messages by channel type and decision
- `clara_faculty_calls_total` - Faculty invocations by name and status
- `clara_rumination_latency_seconds` - Time for Clara to think

## Troubleshooting

### Agent can't reach Discord bot
- Ensure both services are in the same Railway project/environment
- Check that Discord bot is exposing port 9090
- Try using the Railway private domain: `discord.railway.internal:9090`

### No metrics in Grafana
- Check agent logs for scrape errors
- Verify credentials are correct
- Ensure API key has `MetricsPublisher` role
