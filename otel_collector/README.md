# OpenTelemetry Collector for Clara Metrics

Scrapes Prometheus metrics from the Discord bot and pushes to Grafana Cloud.

## Railway Environment Variables

| Variable | Value |
|----------|-------|
| `METRICS_TARGET` | `discord.railway.internal:9090` |
| `PROMETHEUS_REMOTE_WRITE_URL` | `https://prometheus-prod-56-prod-us-east-2.grafana.net/api/prom/push` |
| `PROMETHEUS_USERNAME` | `2910401` |
| `PROMETHEUS_PASSWORD` | Your Grafana Cloud API key |
