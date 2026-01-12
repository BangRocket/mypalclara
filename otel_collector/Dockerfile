FROM otel/opentelemetry-collector-contrib:latest

COPY config.yaml /etc/otelcol-contrib/config.yaml

# Metrics scraping target
ENV METRICS_TARGET=discord.railway.internal:9090

# Grafana Cloud OTLP export
ENV OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-east-2.grafana.net/otlp
ENV GRAFANA_INSTANCE_ID=1493084
ENV GRAFANA_API_KEY=

# Resource attributes for traces
ENV OTEL_SERVICE_NAMESPACE=mypalclara
ENV OTEL_DEPLOYMENT_ENV=production

# Expose collector ports:
# 4317 - OTLP gRPC receiver (traces from Discord bot)
# 4318 - OTLP HTTP receiver (traces from Discord bot)
# 8888 - Prometheus metrics about the collector itself
# 8889 - Prometheus exporter
EXPOSE 4317 4318 8888 8889

CMD ["--config=/etc/otelcol-contrib/config.yaml"]
