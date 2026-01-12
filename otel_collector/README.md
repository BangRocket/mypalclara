# OpenTelemetry Collector for Clara

Collects metrics and traces from the Discord bot and exports to Grafana Cloud via OTLP.

## Features

- **Metrics**: Scrapes Prometheus metrics from the Discord bot (port 9090)
- **Traces**: Receives OTLP traces from the Discord bot (ports 4317/4318)
- **Export**: Pushes both metrics and traces to Grafana Cloud

## Railway Environment Variables

| Variable | Description |
|----------|-------------|
| `METRICS_TARGET` | Discord bot metrics endpoint (default: `discord.railway.internal:9090`) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Grafana Cloud OTLP endpoint |
| `GRAFANA_INSTANCE_ID` | Grafana Cloud instance ID |
| `GRAFANA_API_KEY` | Grafana Cloud API key (set via Railway secrets) |
| `OTEL_SERVICE_NAMESPACE` | Service namespace for traces (default: `mypalclara`) |
| `OTEL_DEPLOYMENT_ENV` | Deployment environment (default: `production`) |

## Discord Bot Configuration

Set these on the Discord bot service to enable tracing:

| Variable | Description |
|----------|-------------|
| `OTEL_ENABLED` | Enable tracing (default: `true`) |
| `OTEL_SERVICE_NAME` | Service name (default: `clara-discord`) |
| `OTEL_EXPORTER_ENDPOINT` | OTEL collector endpoint: `http://otel-collector.railway.internal:4317` |

## Ports

- `4317` - OTLP gRPC receiver (for traces)
- `4318` - OTLP HTTP receiver (for traces)
- `9090` - Discord bot Prometheus metrics (scraped, not exposed here)
