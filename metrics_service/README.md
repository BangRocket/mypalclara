# Metrics Service

Prometheus + Grafana monitoring stack for MyPalClara's Cortex memory system.

## Quick Start

```bash
# 1. Start the monitoring stack
cd metrics_service
docker-compose up -d

# 2. Start the Discord bot with metrics enabled (default)
poetry run python discord_bot_v2.py

# 3. Open Grafana
open http://localhost:3000
# Login: admin / admin
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Discord Bot    │     │   Prometheus    │     │    Grafana      │
│  (port 9090)    │────▶│   (port 9091)   │────▶│   (port 3000)   │
│  /metrics       │     │   scrapes       │     │   visualizes    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `METRICS_ENABLED` | `true` | Enable/disable metrics server |
| `METRICS_PORT` | `9090` | Port for Prometheus to scrape |

## Endpoints

- **Prometheus**: http://localhost:9091 - Query metrics directly
- **Grafana**: http://localhost:3000 - Dashboards (admin/admin)
- **Bot Metrics**: http://localhost:9090/metrics - Raw Prometheus metrics

## Dashboard Panels

The Cortex dashboard includes:

### Overview
- Memories stored/retrieved (24h)
- Redis/Postgres connection status
- Identity promotions
- Retrieval latency (p95)

### Memory Operations
- Memories stored by type (episodic, identity, etc.)
- Memories retrieved by user

### Latency
- Retrieval latency (p50/p95/p99)
- Store latency
- Embedding latency

### Working Memory & Cache
- Working memory size per user
- Working memory expirations
- Cache hit rate
- Cache size

### Consolidation & Churn
- Consolidation runs (success/failure)
- Patterns extracted, contradictions detected
- High churn memories per user

### Embeddings & API
- Embedding requests by provider
- Context token usage

## Metrics Reference

### Memory Operations
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cortex_memories_stored_total` | Counter | memory_type, user_id | Total memories stored |
| `cortex_memories_retrieved_total` | Counter | user_id | Total memories retrieved |
| `cortex_retrieval_latency_seconds` | Histogram | - | Semantic search latency |
| `cortex_store_latency_seconds` | Histogram | - | Memory store latency |

### Working Memory
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cortex_working_memory_size` | Gauge | user_id | Current working memory count |
| `cortex_working_memory_expired_total` | Counter | user_id | TTL expirations |

### Infrastructure
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cortex_redis_connected` | Gauge | - | Redis status (0/1) |
| `cortex_postgres_connected` | Gauge | - | Postgres status (0/1) |

### Embeddings
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cortex_embedding_requests_total` | Counter | provider | Embedding API calls |
| `cortex_embedding_latency_seconds` | Histogram | - | Embedding generation time |

### Cache
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cortex_cache_hits_total` | Counter | cache_type | Cache hits |
| `cortex_cache_misses_total` | Counter | cache_type | Cache misses |
| `cortex_cache_size` | Gauge | cache_type | Current cache size |

### Churn Detection
| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `cortex_identity_promotions_total` | Counter | - | Memories promoted to identity |
| `cortex_high_churn_memories` | Gauge | user_id | Frequently accessed memories |

## Troubleshooting

### Metrics not appearing in Prometheus

1. Check the bot is exposing metrics:
   ```bash
   curl http://localhost:9090/metrics
   ```

2. Check Prometheus can reach the bot:
   ```bash
   docker-compose exec prometheus wget -qO- http://host.docker.internal:9090/metrics
   ```

3. Check Prometheus targets:
   - Open http://localhost:9091/targets
   - Look for "clara" target status

### Grafana shows "No data"

1. Check Prometheus datasource:
   - Go to Configuration > Data Sources > Prometheus
   - Click "Test" to verify connection

2. Check time range:
   - Metrics only appear after the bot processes messages
   - Try "Last 1 hour" or "Last 6 hours"

### Docker on Linux

If `host.docker.internal` doesn't work on Linux, edit `prometheus/prometheus.yml`:

```yaml
- job_name: "clara"
  static_configs:
    - targets: ["172.17.0.1:9090"]  # Docker bridge IP
```

## Production Deployment

For production, consider:

1. **Persistent storage**: The docker-compose already uses named volumes
2. **Authentication**: Add Grafana auth configuration
3. **Alerting**: Configure Prometheus alertmanager
4. **Retention**: Adjust `--storage.tsdb.retention.time` in docker-compose.yml
