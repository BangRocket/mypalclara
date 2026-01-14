# Grafana Alloy for Clara

Receives OTLP telemetry from the Discord bot and exports to Grafana Cloud.

## Railway Setup

1. Create new service from `alloy/` directory
2. Set root directory to `alloy`
3. Set environment variables:

| Variable | Description |
|----------|-------------|
| `GRAFANA_OTLP_ENDPOINT` | e.g., `https://otlp-gateway-prod-us-east-2.grafana.net/otlp` |
| `GRAFANA_INSTANCE_ID` | Your Grafana Cloud instance ID |
| `GRAFANA_API_KEY` | API key with MetricsPublisher + TracesPublisher scopes |

## Discord Bot Configuration

Set on the Discord bot service:

```
OTEL_EXPORTER_ENDPOINT=http://alloy.railway.internal:4317
```

## Ports

- `4317` - OTLP gRPC receiver
- `4318` - OTLP HTTP receiver
- `12345` - Alloy UI and health checks

## Verify

1. Check Alloy logs for "starting OTLP receiver"
2. Send a message to Clara on Discord
3. In Grafana Cloud → Explore → Traces, query:
   ```
   {resource.service.name="clara-discord"}
   ```
