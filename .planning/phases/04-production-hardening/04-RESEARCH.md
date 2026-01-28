# Phase 4: Production Hardening - Research

**Researched:** 2026-01-27
**Domain:** Async Python WebSocket Gateway Production Hardening
**Confidence:** HIGH

## Summary

Production hardening for an async Python WebSocket gateway requires five key systems: automatic provider restart with exponential backoff, per-user/channel rate limiting using token bucket, comprehensive health checks, structured logging with context, and graceful shutdown with pending task completion. The existing codebase uses websockets 15.0, asyncio, and has signal handling infrastructure in place.

**Key findings:**
- Provider restarts should use the backoff or tenacity library with exponential backoff and jitter to prevent thundering herd
- Token bucket rate limiting can be implemented with redis for distributed systems or in-memory for single-instance
- Health checks should separate liveness (/health) from readiness (/ready) and check critical dependencies async
- Structured logging via structlog with JSON output in production enables query-able observability
- Graceful shutdown must collect pending tasks, attempt completion, then cancel with timeout before exit

**Primary recommendation:** Use tenacity for provider restart (asyncio-native), implement token bucket rate limiting per channel in the router, add /health and /ready endpoints to main.py, integrate structlog for JSON logging in production, and enhance shutdown with pending task completion in main.py's signal handler.

## Standard Stack

The established libraries/tools for production hardening of async Python systems:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tenacity | ^9.0.0 | Retry with exponential backoff | Native asyncio support, mature library (used by OpenStack), handles coroutines |
| structlog | ^25.0.0 | Structured logging | Industry standard for JSON logs, integrates with stdlib logging, excellent asyncio support |
| prometheus-async | ^25.0.0 | Metrics collection | Official Prometheus client extension for asyncio, decorator-based API |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aioshutdown | ^1.0.0 | Graceful shutdown utilities | Simplifies signal handling and task cancellation (optional, can be done manually) |
| backoff | ^2.2.0 | Alternative retry library | Simpler API than tenacity, good for basic exponential backoff |
| fastapi | ^0.115.0 | Health check endpoints | Already in dependencies, add /health and /ready routes |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tenacity | backoff | Simpler but less flexible (no async predicate support) |
| structlog | python-json-logger | Less flexible, no processor pipeline |
| prometheus-async | aioprometheus | More batteries-included but less control |

**Installation:**
```bash
poetry add tenacity structlog prometheus-async
# Optional:
poetry add aioshutdown
```

## Architecture Patterns

### Recommended Project Structure
```
gateway/
├── health.py           # Health check endpoints and dependency checks
├── rate_limiter.py     # Token bucket rate limiting
├── metrics.py          # Prometheus metrics collection
└── restart_manager.py  # Provider restart with backoff

config/
├── logging.py          # Enhanced with structlog integration
└── production.py       # Production-specific config

tests/
├── load/
│   └── locustfile.py   # Load testing scenarios
└── test_health.py      # Health check tests
```

### Pattern 1: Provider Restart with Exponential Backoff
**What:** Auto-restart crashed providers with increasing delays to prevent cascading failures
**When to use:** Any long-running background task that can fail transiently (LLM connections, DB connections)
**Example:**
```python
# Source: https://tenacity.readthedocs.io/en/latest/
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from config.logging import get_logger

logger = get_logger("gateway.restart")

class ProviderRestartManager:
    """Manages provider lifecycle with automatic restart."""

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_exponential(multiplier=1, min=4, max=60),  # 4s, 8s, 16s, 32s, 60s
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def start_provider(self, provider_name: str):
        """Start a provider with automatic retry on failure."""
        logger.info(f"Starting provider: {provider_name}")
        # Your provider initialization logic
        await self._initialize_provider(provider_name)

    async def _initialize_provider(self, provider_name: str):
        """Initialize provider (override in subclass)."""
        pass
```

### Pattern 2: Token Bucket Rate Limiting
**What:** Per-channel rate limiting using token bucket algorithm
**When to use:** Prevent spam and abuse, ensure fair resource allocation
**Example:**
```python
# Source: https://github.com/alexdelorenzo/limiter
import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass

@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: int  # Max tokens
    rate: float    # Tokens per second
    tokens: float = 0.0
    last_update: float = 0.0

    def __post_init__(self):
        self.tokens = self.capacity
        self.last_update = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed."""
        now = time.monotonic()
        elapsed = now - self.last_update

        # Add tokens based on elapsed time
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.rate
        )
        self.last_update = now

        # Try to consume
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

class RateLimiter:
    """Rate limiter using token bucket per channel."""

    def __init__(
        self,
        capacity: int = 10,      # 10 messages burst
        rate: float = 2.0,       # 2 messages per second sustained
    ):
        self.capacity = capacity
        self.rate = rate
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, channel_id: str, user_id: str) -> tuple[bool, float]:
        """Check if request is allowed.

        Returns:
            (allowed, retry_after_seconds)
        """
        key = f"{channel_id}:{user_id}"

        async with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(
                    capacity=self.capacity,
                    rate=self.rate
                )

            bucket = self._buckets[key]
            allowed = bucket.consume()

            if not allowed:
                # Calculate retry after
                retry_after = (1.0 - bucket.tokens) / self.rate
                return False, retry_after

            return True, 0.0
```

### Pattern 3: Comprehensive Health Checks
**What:** Separate liveness and readiness probes with dependency checks
**When to use:** Production deployments, Kubernetes/Docker orchestration
**Example:**
```python
# Source: https://www.index.dev/blog/how-to-implement-health-check-in-python
from fastapi import FastAPI, Response, status
from typing import Any
import asyncio

app = FastAPI()

async def check_database() -> tuple[bool, str]:
    """Check database connectivity."""
    try:
        # Example: ping database
        # await db_session.execute("SELECT 1")
        return True, "ok"
    except Exception as e:
        return False, str(e)

async def check_llm_backend() -> tuple[bool, str]:
    """Check LLM backend availability."""
    try:
        # Example: make a trivial LLM call
        # response = await llm.health_check()
        return True, "ok"
    except Exception as e:
        return False, str(e)

@app.get("/health")
async def liveness():
    """Liveness probe - is the app running?"""
    return {"status": "healthy"}

@app.get("/ready")
async def readiness():
    """Readiness probe - can the app handle traffic?"""
    checks = await asyncio.gather(
        check_database(),
        check_llm_backend(),
        return_exceptions=True
    )

    all_healthy = all(
        check[0] if isinstance(check, tuple) else False
        for check in checks
    )

    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return Response(
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": {
                "database": checks[0][1] if isinstance(checks[0], tuple) else "error",
                "llm": checks[1][1] if isinstance(checks[1], tuple) else "error",
            }
        },
        status_code=status_code
    )
```

### Pattern 4: Structured Logging with Context
**What:** JSON logging with request/user/channel context
**When to use:** All production environments for queryable logs
**Example:**
```python
# Source: https://www.structlog.org/en/stable/logging-best-practices.html
import structlog
from structlog.types import EventDict
import os

def add_gateway_context(
    logger: Any, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add gateway-specific context to logs."""
    # Add from contextvars if available
    return event_dict

def configure_structlog():
    """Configure structlog for production."""
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Production: JSON output
    if os.getenv("ENV") == "production":
        processors.append(structlog.processors.dict_tracebacks)
        processors.append(structlog.processors.JSONRenderer())
    # Development: Pretty console
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Usage in gateway code:
import structlog
log = structlog.get_logger()

async def process_message(request):
    # Bind context for all logs in this scope
    log = log.bind(
        user_id=request.user.id,
        channel_id=request.channel.id,
        request_id=request.id
    )

    log.info("processing_message", content_length=len(request.content))
    # ... processing
    log.info("message_complete", response_length=len(response))
```

### Pattern 5: Graceful Shutdown with Pending Tasks
**What:** Complete or cancel pending tasks before exit
**When to use:** Production deployments to avoid data loss
**Example:**
```python
# Source: https://roguelynn.com/words/asyncio-graceful-shutdowns/
import asyncio
import signal
from config.logging import get_logger

logger = get_logger("gateway.shutdown")

async def shutdown(
    loop: asyncio.AbstractEventLoop,
    signal: signal.Signals = None
):
    """Cleanup tasks tied to the service's shutdown."""
    if signal:
        logger.info(f"Received exit signal {signal.name}")

    # Get all running tasks except current
    tasks = [
        task for task in asyncio.all_tasks()
        if task is not asyncio.current_task()
    ]

    logger.info(f"Cancelling {len(tasks)} outstanding tasks")

    # Give tasks a chance to complete
    done, pending = await asyncio.wait(
        tasks,
        timeout=30.0  # 30 second grace period
    )

    logger.info(f"{len(done)} tasks completed, {len(pending)} tasks cancelled")

    # Cancel remaining tasks
    for task in pending:
        task.cancel()

    # Wait for cancellation
    await asyncio.gather(*pending, return_exceptions=True)

    loop.stop()

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Register signal handlers
    signals = (signal.SIGTERM, signal.SIGINT)
    for sig in signals:
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(loop, signal=s))
        )

    try:
        loop.run_forever()
    finally:
        loop.close()
        logger.info("Successfully shutdown")
```

### Anti-Patterns to Avoid
- **Restart without backoff:** Causes thundering herd, wastes resources
- **Global rate limiting:** Doesn't prevent single-user abuse, affects all users
- **Health checks without timeouts:** Can hang monitoring systems
- **String concatenation in logs:** Defeats structured logging benefits
- **Blocking shutdown:** Doesn't cancel tasks, hangs deployments

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry logic | Custom retry loops with sleep | tenacity or backoff library | Handles edge cases (jitter, max attempts, async support) |
| Rate limiting | Simple counter with timestamp | Token bucket with redis/in-memory | Handles bursts, distributed systems, fairness |
| Structured logging | Manual JSON serialization | structlog with processors | Handles exceptions, context binding, formats |
| Graceful shutdown | Immediate task cancellation | Signal handling with grace period | Prevents data loss, allows cleanup |
| Health checks | Single /health endpoint | Separate /health and /ready | Kubernetes best practice, different purposes |
| Metrics collection | Manual prometheus metrics | prometheus-async decorators | Thread-safe, async-aware, standardized |

**Key insight:** Production hardening is 90% about handling edge cases that only manifest at scale. Libraries like tenacity have seen millions of production hours and handle cases you won't think of until they break.

## Common Pitfalls

### Pitfall 1: Restart Loop Without Backoff
**What goes wrong:** Provider crashes, restarts instantly, crashes again, consuming CPU and logs
**Why it happens:** Naive "while True: try/except/restart" pattern
**How to avoid:** Always use exponential backoff with jitter and max attempts
**Warning signs:** Spikes in restart logs, high CPU with no real work, CloudWatch logs exploding

### Pitfall 2: Rate Limiting Without Burst Allowance
**What goes wrong:** Legitimate users get rate limited when sending multiple quick messages
**Why it happens:** Simple "X requests per second" counter doesn't allow bursts
**How to avoid:** Use token bucket which allows bursts up to capacity but limits sustained rate
**Warning signs:** User complaints about "slow" bot, legitimate requests getting 429s

### Pitfall 3: Health Checks That Don't Check Dependencies
**What goes wrong:** Kubernetes routes traffic to pod that can't reach database
**Why it happens:** Health check only verifies "process is running" not "can do work"
**How to avoid:** Readiness probe must check all critical dependencies (DB, LLM, etc.)
**Warning signs:** 502/504 errors despite healthy pods, increased error rates after deployments

### Pitfall 4: Unstructured Logs at Scale
**What goes wrong:** Can't debug production issues, can't query logs efficiently
**Why it happens:** String formatting in logs doesn't translate to structured data
**How to avoid:** Use structlog with JSONRenderer in production from day one
**Warning signs:** "I can't find why user X's request failed", grep through millions of lines

### Pitfall 5: Memory Leaks in Long-Running Async Tasks
**What goes wrong:** Gateway memory grows over days/weeks until OOM crash
**Why it happens:** Unclosed connections, circular references, large message queues
**How to avoid:** Monitor memory metrics, set max_queue and max_size on websockets, cleanup stale sessions
**Warning signs:** Steady memory growth, increased GC pressure, eventual OOM kills

### Pitfall 6: Blocking Calls in Async Context
**What goes wrong:** Single slow DB query blocks entire event loop, all connections stall
**Why it happens:** Using sync libraries in async functions without run_in_executor
**How to avoid:** Use only async-native libraries or wrap in executor, never use time.sleep()
**Warning signs:** All requests slow down together, high latency on unrelated operations

### Pitfall 7: No Resource Limits on Websockets
**What goes wrong:** Single malicious client sends huge messages, crashes gateway
**Why it happens:** Default websockets settings allow unlimited message size
**How to avoid:** Set max_size, max_queue, read_limit, write_limit on websocket server
**Warning signs:** Sudden memory spikes, OOM with small connection count

## Code Examples

Verified patterns from official sources:

### Rate Limiter Integration in Server
```python
# Source: Gateway router.py pattern + token bucket
from gateway.rate_limiter import RateLimiter
from gateway.protocol import ErrorMessage, MessageRequest

class GatewayServer:
    def __init__(self, ...):
        # ... existing init
        self.rate_limiter = RateLimiter(
            capacity=int(os.getenv("RATE_LIMIT_BURST", "10")),
            rate=float(os.getenv("RATE_LIMIT_PER_SEC", "2.0"))
        )

    async def _handle_message_request(
        self,
        websocket: WebSocketServerProtocol,
        msg: MessageRequest,
    ) -> None:
        """Handle message with rate limiting."""
        # Check rate limit
        allowed, retry_after = await self.rate_limiter.check_rate_limit(
            channel_id=msg.channel.id,
            user_id=msg.user.id
        )

        if not allowed:
            await self._send_error(
                websocket,
                msg.id,
                "rate_limited",
                f"Rate limit exceeded. Retry after {retry_after:.1f}s",
                recoverable=True
            )
            return

        # Existing request handling...
        self._message_count += 1
        # ...
```

### Health Check Endpoints in main.py
```python
# Source: FastAPI health check pattern
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
import uvicorn

# Add to gateway/main.py
health_app = FastAPI()

@health_app.get("/health")
async def health():
    """Liveness probe."""
    return {"status": "healthy"}

@health_app.get("/ready")
async def ready():
    """Readiness probe - checks dependencies."""
    checks = {
        "websocket_server": server._server is not None,
        "processor": processor._initialized,
        "memory_manager": processor._memory_manager is not None,
    }

    all_ready = all(checks.values())

    return JSONResponse(
        content={
            "status": "ready" if all_ready else "not_ready",
            "checks": checks
        },
        status_code=status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    )

# Run health server in background thread
def run_health_server(port: int = 8080):
    uvicorn.run(health_app, host="0.0.0.0", port=port, log_level="warning")

# In main():
import threading
health_thread = threading.Thread(
    target=run_health_server,
    args=(int(os.getenv("HEALTH_PORT", "8080")),),
    daemon=True
)
health_thread.start()
```

### Prometheus Metrics Collection
```python
# Source: https://prometheus-async.readthedocs.io/en/stable/asyncio.html
from prometheus_async import aio
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
messages_processed = Counter(
    "gateway_messages_processed_total",
    "Total messages processed",
    ["platform", "channel_type"]
)

processing_duration = Histogram(
    "gateway_processing_duration_seconds",
    "Message processing duration",
    ["platform"]
)

active_connections = Gauge(
    "gateway_active_connections",
    "Number of active WebSocket connections",
    ["platform"]
)

# Use in code
@aio.time(processing_duration.labels(platform="discord"))
async def process_message(request):
    """Process message with timing."""
    # ... processing
    messages_processed.labels(
        platform=request.metadata.get("platform"),
        channel_type=request.channel.type
    ).inc()
```

### Structured Logging in Processor
```python
# Source: https://www.structlog.org/en/stable/
import structlog

class MessageProcessor:
    def __init__(self):
        self.log = structlog.get_logger("gateway.processor")

    async def process(self, request, websocket, server):
        # Bind context for this request
        log = self.log.bind(
            request_id=request.id,
            user_id=request.user.id,
            channel_id=request.channel.id,
            platform=request.metadata.get("platform")
        )

        log.info("message_received", content_length=len(request.content))

        try:
            # ... processing
            log.info("message_complete",
                response_length=len(full_text),
                tool_count=tool_count,
                duration_ms=int(duration * 1000)
            )
        except Exception as e:
            log.error("processing_error",
                error_type=type(e).__name__,
                error_message=str(e),
                exc_info=True
            )
            raise
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Python logging with string formatting | structlog with JSON output | 2020-2021 | Queryable logs, better observability |
| Manual retry loops | tenacity/backoff decorators | 2018-2019 | Fewer bugs, better jitter handling |
| Simple request counters | Token bucket rate limiting | 2019-2020 | Fairer, handles bursts better |
| Single /health endpoint | Separate /live and /ready | 2021 (K8s best practice) | Better orchestration, fewer false positives |
| gevent for async (Locust) | Native asyncio everywhere | 2023-2024 | Better ecosystem, no greenlet patching |
| prometheus_client only | prometheus-async for asyncio | 2020 | Correct async metrics, no blocking |

**Deprecated/outdated:**
- **aiohttp for health endpoints**: FastAPI is now standard (better DX, OpenAPI docs)
- **Custom backoff implementations**: Use tenacity (battle-tested, more features)
- **String-based logging**: Always use structured logging (JSON in prod)

## Load Testing Approaches

### Locust for WebSocket Testing
```python
# tests/load/locustfile.py
# Source: https://docs.locust.io/en/stable/testing-other-systems.html
import json
import time
from locust import User, task, between
from locust.exception import RescheduleTask
import websocket

class WebSocketClient:
    def __init__(self, host):
        self.host = host
        self.ws = None

    def connect(self):
        self.ws = websocket.create_connection(self.host)

    def send_message(self, message):
        start_time = time.time()
        try:
            self.ws.send(json.dumps(message))
            response = self.ws.recv()
            total_time = int((time.time() - start_time) * 1000)
            return response, total_time
        except Exception as e:
            total_time = int((time.time() - start_time) * 1000)
            raise e

    def disconnect(self):
        if self.ws:
            self.ws.close()

class GatewayUser(User):
    wait_time = between(1, 5)

    def on_start(self):
        """Connect when user starts."""
        self.client = WebSocketClient(f"ws://{self.host}")
        self.client.connect()

        # Register adapter
        register_msg = {
            "type": "register",
            "node_id": f"test-node-{self.context_id}",
            "platform": "load_test"
        }
        self.client.send_message(register_msg)

    def on_stop(self):
        """Disconnect when user stops."""
        self.client.disconnect()

    @task
    def send_message(self):
        """Send a test message."""
        message = {
            "type": "message",
            "id": f"req-{time.time()}",
            "content": "Test message",
            "user": {"id": f"user-{self.context_id}"},
            "channel": {"id": "test-channel", "type": "dm"}
        }

        try:
            response, response_time = self.client.send_message(message)
            # Record success
            self.environment.events.request.fire(
                request_type="WebSocket",
                name="send_message",
                response_time=response_time,
                response_length=len(response),
                exception=None,
                context={}
            )
        except Exception as e:
            # Record failure
            self.environment.events.request.fire(
                request_type="WebSocket",
                name="send_message",
                response_time=0,
                response_length=0,
                exception=e,
                context={}
            )
```

Run with: `locust -f tests/load/locustfile.py --host=127.0.0.1:18789 --users=100 --spawn-rate=10`

### Pure Asyncio Load Testing
```python
# Alternative: tests/load/async_load_test.py
import asyncio
import websockets
import json
import time
from statistics import mean, median

async def simulate_client(client_id: int, duration_seconds: int = 60):
    """Simulate a single client."""
    uri = "ws://127.0.0.1:18789"
    latencies = []
    errors = 0

    try:
        async with websockets.connect(uri) as ws:
            # Register
            await ws.send(json.dumps({
                "type": "register",
                "node_id": f"test-{client_id}",
                "platform": "load_test"
            }))
            await ws.recv()

            # Send messages for duration
            end_time = time.time() + duration_seconds
            while time.time() < end_time:
                start = time.time()

                await ws.send(json.dumps({
                    "type": "message",
                    "id": f"req-{client_id}-{time.time()}",
                    "content": "Load test message",
                    "user": {"id": f"user-{client_id}"},
                    "channel": {"id": "test", "type": "dm"}
                }))

                response = await ws.recv()
                latency = (time.time() - start) * 1000
                latencies.append(latency)

                await asyncio.sleep(1)  # 1 message per second per client

    except Exception as e:
        errors += 1
        print(f"Client {client_id} error: {e}")

    return latencies, errors

async def run_load_test(num_clients: int = 100, duration: int = 60):
    """Run load test with concurrent clients."""
    print(f"Starting load test: {num_clients} clients for {duration}s")

    tasks = [
        simulate_client(i, duration)
        for i in range(num_clients)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate results
    all_latencies = []
    total_errors = 0

    for result in results:
        if isinstance(result, tuple):
            latencies, errors = result
            all_latencies.extend(latencies)
            total_errors += errors

    # Print summary
    print(f"\nLoad Test Results:")
    print(f"  Total requests: {len(all_latencies)}")
    print(f"  Total errors: {total_errors}")
    print(f"  Mean latency: {mean(all_latencies):.2f}ms")
    print(f"  Median latency: {median(all_latencies):.2f}ms")
    print(f"  P95 latency: {sorted(all_latencies)[int(len(all_latencies) * 0.95)]:.2f}ms")
    print(f"  P99 latency: {sorted(all_latencies)[int(len(all_latencies) * 0.99)]:.2f}ms")

if __name__ == "__main__":
    asyncio.run(run_load_test(num_clients=100, duration=60))
```

## Open Questions

Things that couldn't be fully resolved:

1. **Discord Monitor Integration**
   - What we know: No discord_monitor.py file found in codebase (search returned no results)
   - What's unclear: Whether monitoring dashboard needs to be built from scratch or integrated differently
   - Recommendation: Create new monitoring dashboard or skip if not critical for gateway (Discord bot has separate monitoring at port 8001)

2. **Optimal Rate Limit Values**
   - What we know: Token bucket with burst=10, rate=2/s is common pattern
   - What's unclear: Actual usage patterns and appropriate limits for this application
   - Recommendation: Start conservative (burst=5, rate=1/s), monitor metrics, adjust based on 95th percentile usage

3. **Memory Limits Per Connection**
   - What we know: websockets 15.0 defaults to 64 KiB per connection, can be reduced to 14 KiB
   - What's unclear: Expected message sizes and whether compression should be enabled
   - Recommendation: Profile actual message sizes, set max_size accordingly, disable compression if messages are small (<1KB)

4. **Distributed Rate Limiting**
   - What we know: Redis-based token bucket works for multi-instance deployments
   - What's unclear: Whether gateway will run as single instance or multiple instances
   - Recommendation: Implement in-memory rate limiting initially, add Redis support if scaling to multiple instances

## Sources

### Primary (HIGH confidence)
- [Tenacity Documentation](https://tenacity.readthedocs.io/en/latest/) - Retry patterns for asyncio
- [Structlog Documentation](https://www.structlog.org/en/stable/logging-best-practices.html) - Structured logging best practices
- [Prometheus-async Documentation](https://prometheus-async.readthedocs.io/en/stable/asyncio.html) - Asyncio metrics collection
- [Websockets Documentation](https://websockets.readthedocs.io/en/stable/topics/memory.html) - Memory and resource limits
- [FastAPI Health Check Guide](https://www.index.dev/blog/how-to-implement-health-check-in-python) - Health check implementation

### Secondary (MEDIUM confidence)
- [Backoff Library on PyPI](https://pypi.org/project/backoff/) - Alternative retry library
- [Limiter Library on GitHub](https://github.com/alexdelorenzo/limiter) - Token bucket rate limiting
- [Locust Documentation](https://docs.locust.io/en/stable/testing-other-systems.html) - WebSocket load testing
- [Graceful Shutdowns with asyncio](https://roguelynn.com/words/asyncio-graceful-shutdowns/) - Shutdown patterns
- [aiotools Documentation](https://aiotools.readthedocs.io/en/latest/aiotools.server.html) - Signal handling utilities

### Tertiary (LOW confidence)
- [C-Sharp Corner Rate Limiting Article](https://www.c-sharpcorner.com/article/rate-limiting-using-the-token-bucket-algorithm-for-api-gateway-protection-using/) - Token bucket algorithm explanation
- [Medium Articles on Retry Mechanisms](https://medium.com/@oggy/retry-mechanisms-in-python-practical-guide-with-real-life-examples-ed323e7a8871) - Retry patterns
- [Better Stack Structlog Guide](https://betterstack.com/community/guides/logging/structlog/) - Structlog patterns
- [HackerNoon Asyncio Shutdown](https://hackernoon.com/asyncio-how-to-say-goodbye-without-losing-your-data) - Graceful shutdown

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Libraries are mature, widely used, and have asyncio support
- Architecture patterns: HIGH - Patterns verified from official documentation and production use
- Pitfalls: HIGH - Based on documented production issues and best practices
- Load testing: MEDIUM - Locust WebSocket support is via plugins, asyncio approach is custom but straightforward
- Integration details: MEDIUM - Some decisions depend on deployment architecture (single vs multi-instance)

**Research date:** 2026-01-27
**Valid until:** 2026-02-27 (30 days - stable ecosystem, patterns are well-established)

**Key takeaway:** Production hardening is about preventing cascading failures. Provider restarts need backoff to avoid thundering herd. Rate limiting prevents single-user abuse. Health checks must verify dependencies. Structured logs enable debugging. Graceful shutdown prevents data loss. These patterns are battle-tested across thousands of production services.
