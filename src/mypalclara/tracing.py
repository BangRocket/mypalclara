"""
OpenTelemetry Tracing - Distributed tracing for the Discord bot.

Exports traces to Grafana Cloud via OTLP through the OTEL collector.

Usage:
    from mypalclara.tracing import init_tracing, tracer

    # Initialize at startup
    init_tracing()

    # Create spans
    with tracer.start_as_current_span("my-operation") as span:
        span.set_attribute("key", "value")
        # do work
"""

import logging
import os

logger = logging.getLogger(__name__)

# Global tracer instance
tracer = None
_initialized = False


def init_tracing() -> bool:
    """
    Initialize OpenTelemetry tracing with OTLP exporter.

    Environment variables:
        OTEL_ENABLED: Enable tracing (default: true)
        OTEL_SERVICE_NAME: Service name (default: clara-discord)
        OTEL_SERVICE_NAMESPACE: Service namespace (default: mypalclara)
        OTEL_DEPLOYMENT_ENV: Deployment environment (default: production)
        OTEL_EXPORTER_ENDPOINT: OTLP endpoint (default: http://localhost:4317)

    Returns:
        True if tracing initialized, False if disabled or failed
    """
    global tracer, _initialized

    if _initialized:
        logger.warning("Tracing already initialized")
        return True

    # Check if tracing is enabled
    if os.environ.get("OTEL_ENABLED", "true").lower() not in ("true", "1", "yes"):
        logger.info("Tracing disabled via OTEL_ENABLED")
        _init_noop_tracer()
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "opentelemetry packages not installed, tracing disabled. "
            "Install with: poetry add opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
        )
        _init_noop_tracer()
        return False

    try:
        # Get configuration from environment
        service_name = os.environ.get("OTEL_SERVICE_NAME", "clara-discord")
        service_namespace = os.environ.get("OTEL_SERVICE_NAMESPACE", "mypalclara")
        deployment_env = os.environ.get("OTEL_DEPLOYMENT_ENV", "production")
        endpoint = os.environ.get("OTEL_EXPORTER_ENDPOINT", "http://localhost:4317")

        # Create resource with attributes that Grafana Cloud expects
        resource = Resource.create({
            "service.name": service_name,
            "service.namespace": service_namespace,
            "deployment.environment": deployment_env,
            "service.version": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev")[:8],
        })

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=endpoint,
            insecure=not endpoint.startswith("https://"),
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Set as global tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer instance
        tracer = trace.get_tracer(__name__)

        # Auto-instrument libraries
        _auto_instrument()

        _initialized = True
        logger.info(f"Tracing initialized: service={service_name}, endpoint={endpoint}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize tracing: {e}")
        _init_noop_tracer()
        return False


def _init_noop_tracer():
    """Initialize a no-op tracer for when tracing is disabled."""
    global tracer, _initialized
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)
    _initialized = True


def _auto_instrument():
    """Auto-instrument common libraries."""
    # Instrument httpx (used for LLM API calls)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentation
        HTTPXClientInstrumentation().instrument()
        logger.debug("Instrumented httpx")
    except Exception as e:
        logger.debug(f"Could not instrument httpx: {e}")

    # Instrument SQLAlchemy (used for database)
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument()
        logger.debug("Instrumented SQLAlchemy")
    except Exception as e:
        logger.debug(f"Could not instrument SQLAlchemy: {e}")


def get_tracer(name: str = __name__):
    """Get a tracer instance for creating spans."""
    global tracer
    if tracer is None:
        _init_noop_tracer()
    from opentelemetry import trace
    return trace.get_tracer(name)


def is_tracing_enabled() -> bool:
    """Check if tracing is enabled via environment."""
    return os.environ.get("OTEL_ENABLED", "true").lower() in ("true", "1", "yes")


def get_otel_endpoint() -> str:
    """Get the configured OTLP endpoint."""
    return os.environ.get("OTEL_EXPORTER_ENDPOINT", "http://localhost:4317")
