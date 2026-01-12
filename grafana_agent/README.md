# Grafana Alloy for Clara Metrics

Scrapes Prometheus metrics from the Discord bot and pushes to Grafana Cloud.

## Railway Environment Variables

Set these on the grafana-agent Railway service:

| Variable | Value |
|----------|-------|
| `GCLOUD_HOSTED_METRICS_ID` | `2910401` |
| `GCLOUD_HOSTED_METRICS_URL` | `https://prometheus-prod-56-prod-us-east-2.grafana.net/api/prom/push` |
| `GCLOUD_HOSTED_LOGS_ID` | `1450877` |
| `GCLOUD_HOSTED_LOGS_URL` | `https://logs-prod-036.grafana.net/loki/api/v1/push` |
| `GCLOUD_FM_URL` | `https://fleet-management-prod-008.grafana.net` |
| `GCLOUD_FM_POLL_FREQUENCY` | `60s` |
| `GCLOUD_FM_HOSTED_ID` | `1493084` |
| `GCLOUD_RW_API_KEY` | Your API key |
| `METRICS_TARGET` | `discord.railway.internal:9090` |

## Verify

1. Check Railway logs for successful scrapes
2. In Grafana Cloud, go to **Explore** → select your Prometheus datasource
3. Query for `cortex_` or `clara_` metrics
