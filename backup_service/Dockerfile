FROM python:3.12-slim

# Install PostgreSQL client tools (pg_dump, psql)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backup script
COPY backup.py .

# Expose health check port
EXPOSE 8080

# Run backup
CMD ["python", "backup.py"]
