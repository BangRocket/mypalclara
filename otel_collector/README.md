# OpenTelemetry Collector for Clara Metrics

Scrapes Prometheus metrics from the Discord bot and pushes to Grafana Cloud via OTLP.

## Railway Environment Variables

| Variable | Value |
|----------|-------|
| `METRICS_TARGET` | `discord.railway.internal:9090` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `https://otlp-gateway-prod-us-east-2.grafana.net/otlp` |
| `GRAFANA_INSTANCE_ID` | `1493084` |
| `GRAFANA_API_KEY` | `<your-grafana-cloud-api-key>` |
