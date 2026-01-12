FROM otel/opentelemetry-collector-contrib:latest

COPY config.yaml /etc/otelcol-contrib/config.yaml

ENV METRICS_TARGET=discord.railway.internal:9090
ENV PROMETHEUS_REMOTE_WRITE_URL=https://prometheus-prod-56-prod-us-east-2.grafana.net/api/prom/push
ENV PROMETHEUS_USERNAME=2910401
ENV PROMETHEUS_PASSWORD=

EXPOSE 8888 8889

CMD ["--config=/etc/otelcol-contrib/config.yaml"]
