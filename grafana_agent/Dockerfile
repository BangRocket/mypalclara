FROM grafana/agent:latest

COPY agent.yaml /etc/agent/agent.yaml

# Grafana Agent uses environment variable substitution in config
# Set defaults that can be overridden
ENV METRICS_TARGET=discord.railway.internal:9090
ENV RAILWAY_ENVIRONMENT=stage

EXPOSE 12345

ENTRYPOINT ["/bin/grafana-agent", "-config.file=/etc/agent/agent.yaml", "-config.expand-env=true"]
