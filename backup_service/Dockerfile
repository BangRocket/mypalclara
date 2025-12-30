FROM python:3.12-slim

# Install PostgreSQL client for pg_dump
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir boto3

# Copy backup script
COPY backup.py .

# Run backup on container start
CMD ["python", "backup.py"]
