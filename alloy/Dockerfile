FROM grafana/alloy:latest

COPY config.alloy /etc/alloy/config.alloy

# Grafana Cloud credentials (set via Railway env vars)
ENV GRAFANA_OTLP_ENDPOINT=https://otlp-gateway-prod-us-east-2.grafana.net/otlp
ENV GRAFANA_INSTANCE_ID=
ENV GRAFANA_API_KEY=

# OTLP receiver ports
EXPOSE 4317 4318

# Health check / metrics port
EXPOSE 12345

ENTRYPOINT ["/bin/alloy"]
CMD ["run", "--server.http.listen-addr=0.0.0.0:12345", "/etc/alloy/config.alloy"]
