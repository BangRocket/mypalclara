# Grafana Alloy for Clara Metrics

Scrapes Prometheus metrics from the Discord bot and pushes to Grafana Cloud.

## Setup

### 1. Deploy to Railway

1. Create a new service in Railway from this directory
2. Set root directory to `grafana_agent`
3. Set environment variables:

| Variable | Value |
|----------|-------|
| `GRAFANA_REMOTE_WRITE_URL` | `https://prometheus-prod-56-prod-us-east-2.grafana.net/api/prom/push` |
| `GRAFANA_CLOUD_USER` | `2910401` |
| `GRAFANA_CLOUD_API_KEY` | Your API key |
| `METRICS_TARGET` | `discord.railway.internal:9090` |

### 2. Verify

1. Check Railway logs for successful scrapes
2. In Grafana Cloud, go to **Explore** → select your Prometheus datasource
3. Query for `cortex_` or `clara_` metrics
