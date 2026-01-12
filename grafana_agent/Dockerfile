FROM grafana/alloy:latest

# Fleet management mode - Grafana Cloud manages the config remotely
ENV GCLOUD_HOSTED_METRICS_ID=""
ENV GCLOUD_HOSTED_METRICS_URL=""
ENV GCLOUD_HOSTED_LOGS_ID=""
ENV GCLOUD_HOSTED_LOGS_URL=""
ENV GCLOUD_FM_URL=""
ENV GCLOUD_FM_POLL_FREQUENCY="60s"
ENV GCLOUD_FM_HOSTED_ID=""
ENV GCLOUD_RW_API_KEY=""

# Local scrape target (the discord bot)
ENV METRICS_TARGET="discord.railway.internal:9090"

# Copy a minimal bootstrap config that sets up fleet management
COPY config.alloy /etc/alloy/config.alloy

EXPOSE 12345

ENTRYPOINT ["/bin/alloy", "run", "/etc/alloy/config.alloy", "--storage.path=/tmp/alloy"]
