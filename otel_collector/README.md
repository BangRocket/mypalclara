# OpenTelemetry Collector for Clara Metrics

Scrapes Prometheus metrics from the Discord bot and pushes to Grafana Cloud via OTLP.

## Railway Environment Variables

| Variable | Value |
|----------|-------|
| `METRICS_TARGET` | `discord.railway.internal:9090` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `https://otlp-gateway-prod-us-east-2.grafana.net/otlp` |
| `OTEL_EXPORTER_OTLP_AUTH` | `Basic Z2xjX2V5SnZJam9pTVRZek9USTROeUlzSW00aU9pSnpkR0ZqYXkweE5Ea3pNRGcwTFdGc2JHOTVMVzE1Y0dGc1pteHZJaXdpYXlJNklqZFhVVGRxTXpaUVZ6aDNVWGxxV0RkSWVUVTFiazAzT1NJc0ltMGlPbnNpY2lJNkluQnliMlF0ZFhNdFpXRnpkQzB3SW4xOToxNDkzMDg0` |

Note: The auth value is the URL-decoded version of the header (replace `%20` with space).
