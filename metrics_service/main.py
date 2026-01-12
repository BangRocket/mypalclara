"""
Metrics Service - Exposes Prometheus metrics for Cortex memory system.

This service runs alongside the Discord bot and exposes metrics at /metrics
for Prometheus to scrape.

Run with: uvicorn main:app --host 0.0.0.0 --port 9090
"""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)

# Check if we're in multiprocess mode (for gunicorn)
if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
else:
    registry = CollectorRegistry(auto_describe=True)

# ==================== METRICS DEFINITIONS ====================

# Memory Operations
memories_stored = Counter(
    "cortex_memories_stored_total",
    "Total memories stored",
    ["memory_type", "user_id"],
    registry=registry,
)

memories_retrieved = Counter(
    "cortex_memories_retrieved_total",
    "Total memories retrieved",
    ["user_id"],
    registry=registry,
)

retrieval_latency = Histogram(
    "cortex_retrieval_latency_seconds",
    "Memory retrieval latency",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    registry=registry,
)

store_latency = Histogram(
    "cortex_store_latency_seconds",
    "Memory store latency",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    registry=registry,
)

# Working Memory
working_memory_size = Gauge(
    "cortex_working_memory_size",
    "Current working memory count",
    ["user_id"],
    registry=registry,
)

working_memory_expired = Counter(
    "cortex_working_memory_expired_total",
    "Working memories expired by TTL",
    ["user_id"],
    registry=registry,
)

# Consolidation
consolidation_runs = Counter(
    "cortex_consolidation_runs_total",
    "Consolidation job runs",
    ["status"],
    registry=registry,
)

patterns_extracted = Counter(
    "cortex_patterns_extracted_total",
    "Patterns extracted during consolidation",
    registry=registry,
)

contradictions_detected = Counter(
    "cortex_contradictions_detected_total",
    "Memory contradictions detected",
    registry=registry,
)

memories_compacted = Counter(
    "cortex_memories_compacted_total",
    "Memories compacted/merged",
    registry=registry,
)

# Infrastructure
redis_connected = Gauge(
    "cortex_redis_connected",
    "Redis connection status",
    registry=registry,
)

postgres_connected = Gauge(
    "cortex_postgres_connected",
    "Postgres connection status",
    registry=registry,
)

# Embeddings
embedding_requests = Counter(
    "cortex_embedding_requests_total",
    "Embedding API requests",
    ["provider"],
    registry=registry,
)

embedding_latency = Histogram(
    "cortex_embedding_latency_seconds",
    "Embedding generation latency",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=registry,
)

# Cache
cache_hits = Counter(
    "cortex_cache_hits_total",
    "Cache hits",
    ["cache_type"],
    registry=registry,
)

cache_misses = Counter(
    "cortex_cache_misses_total",
    "Cache misses",
    ["cache_type"],
    registry=registry,
)

cache_size = Gauge(
    "cortex_cache_size",
    "Current cache size",
    ["cache_type"],
    registry=registry,
)

# Token Budget
budget_applications = Counter(
    "cortex_budget_applications_total",
    "Token budget applications",
    ["action"],
    registry=registry,
)

context_tokens = Histogram(
    "cortex_context_tokens",
    "Tokens in context",
    buckets=[100, 500, 1000, 2000, 4000, 8000, 16000],
    registry=registry,
)

# Churn/Identity
identity_promotions = Counter(
    "cortex_identity_promotions_total",
    "Memories promoted to identity",
    registry=registry,
)

high_churn_memories = Gauge(
    "cortex_high_churn_memories",
    "High-churn memory count",
    ["user_id"],
    registry=registry,
)

# Clara-specific metrics
clara_messages_processed = Counter(
    "clara_messages_processed_total",
    "Messages processed by Clara",
    ["channel_type", "decision"],
    registry=registry,
)

clara_faculty_calls = Counter(
    "clara_faculty_calls_total",
    "Faculty (capability) invocations",
    ["faculty", "status"],
    registry=registry,
)

clara_rumination_latency = Histogram(
    "clara_rumination_latency_seconds",
    "Time for Clara to think",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry,
)


# ==================== FASTAPI APP ====================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan - startup and shutdown."""
    # Could connect to Redis here to pull live stats
    yield


app = FastAPI(
    title="Cortex Metrics",
    description="Prometheus metrics for MyPalClara's Cortex memory system",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/")
async def root():
    """Root endpoint with info."""
    return {
        "service": "cortex-metrics",
        "endpoints": {
            "/health": "Health check",
            "/metrics": "Prometheus metrics",
        },
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 9090))
    uvicorn.run(app, host="0.0.0.0", port=port)
