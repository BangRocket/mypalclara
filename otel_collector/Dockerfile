FROM otel/opentelemetry-collector-contrib:latest

COPY config.yaml /etc/otelcol-contrib/config.yaml

ENV METRICS_TARGET=discord.railway.internal:9090
ENV OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-us-east-2.grafana.net/otlp
ENV OTEL_EXPORTER_OTLP_AUTH=

EXPOSE 8888 8889

CMD ["--config=/etc/otelcol-contrib/config.yaml"]
