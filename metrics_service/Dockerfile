FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Railway sets PORT env var
ENV PORT=9090
EXPOSE 9090

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
