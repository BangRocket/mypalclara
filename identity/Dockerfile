FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry

COPY identity/pyproject.toml identity/poetry.lock* ./
RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

COPY identity/ ./identity/

RUN groupadd --system --gid 1000 app && \
    useradd app --uid 1000 --gid 1000 --create-home --shell /bin/bash
USER app:app

EXPOSE 18791

CMD ["python", "-m", "identity.main"]
