FROM grafana/alloy:latest

COPY config.alloy /etc/alloy/config.alloy

ENV METRICS_TARGET=discord.railway.internal:9090

EXPOSE 12345

ENTRYPOINT ["/bin/alloy", "run", "/etc/alloy/config.alloy", "--storage.path=/tmp/alloy"]
