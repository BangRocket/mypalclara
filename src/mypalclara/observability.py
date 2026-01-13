"""
Observability - Direct export of traces and metrics to Grafana Cloud.

No collector needed - exports directly via OTLP to Grafana Cloud.

Usage:
    from mypalclara.observability import init_observability, get_tracer, get_meter

    # Initialize at startup (once)
    init_observability()

    # Create traces
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my-operation") as span:
        span.set_attribute("key", "value")

    # Create metrics
    meter = get_meter(__name__)
    counter = meter.create_counter("my_counter")
    counter.add(1, {"label": "value"})

Environment Variables:
    GRAFANA_OTLP_ENDPOINT: Grafana Cloud OTLP endpoint (required)
    GRAFANA_INSTANCE_ID: Grafana Cloud instance ID (required)
    GRAFANA_API_KEY: Grafana Cloud API key (required)
    OTEL_SERVICE_NAME: Service name (default: clara-discord)
    OTEL_SERVICE_NAMESPACE: Namespace (default: mypalclara)
    OTEL_DEPLOYMENT_ENV: Environment (default: production)
    OTEL_ENABLED: Enable observability (default: true)
"""

import base64
import logging
import os

logger = logging.getLogger(__name__)

_initialized = False
_tracer = None
_meter = None


def init_observability() -> bool:
    """
    Initialize OpenTelemetry with direct export to Grafana Cloud.

    Returns:
        True if initialized successfully, False otherwise
    """
    global _initialized, _tracer, _meter

    if _initialized:
        logger.debug("Observability already initialized")
        return True

    # Check if enabled
    if os.environ.get("OTEL_ENABLED", "true").lower() not in ("true", "1", "yes"):
        logger.info("Observability disabled via OTEL_ENABLED=false")
        _init_noop()
        return False

    # Check for required Grafana Cloud config
    endpoint = os.environ.get("GRAFANA_OTLP_ENDPOINT")
    instance_id = os.environ.get("GRAFANA_INSTANCE_ID")
    api_key = os.environ.get("GRAFANA_API_KEY")

    if not all([endpoint, instance_id, api_key]):
        logger.warning(
            "Grafana Cloud not configured (missing GRAFANA_OTLP_ENDPOINT, "
            "GRAFANA_INSTANCE_ID, or GRAFANA_API_KEY). Observability disabled."
        )
        _init_noop()
        return False

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as e:
        logger.warning(f"OpenTelemetry packages not installed: {e}")
        _init_noop()
        return False

    try:
        # Get service configuration
        service_name = os.environ.get("OTEL_SERVICE_NAME", "clara-discord")
        service_namespace = os.environ.get("OTEL_SERVICE_NAMESPACE", "mypalclara")
        deployment_env = os.environ.get("OTEL_DEPLOYMENT_ENV", "production")

        # Create resource with attributes Grafana Cloud expects
        resource = Resource.create({
            "service.name": service_name,
            "service.namespace": service_namespace,
            "deployment.environment": deployment_env,
            "service.version": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev")[:8],
        })

        # Build auth header for Grafana Cloud
        # Format: Basic base64(instance_id:api_key)
        auth_string = f"{instance_id}:{api_key}"
        auth_bytes = base64.b64encode(auth_string.encode()).decode()
        headers = {"Authorization": f"Basic {auth_bytes}"}

        # Initialize Traces
        trace_exporter = OTLPSpanExporter(
            endpoint=f"{endpoint}/v1/traces",
            headers=headers,
        )
        trace_provider = TracerProvider(resource=resource)
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        trace.set_tracer_provider(trace_provider)

        # Initialize Metrics
        metric_exporter = OTLPMetricExporter(
            endpoint=f"{endpoint}/v1/metrics",
            headers=headers,
        )
        metric_reader = PeriodicExportingMetricReader(
            metric_exporter,
            export_interval_millis=60000,  # Export every 60 seconds
        )
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
        )
        metrics.set_meter_provider(meter_provider)

        # Store references
        _tracer = trace.get_tracer(__name__)
        _meter = metrics.get_meter(__name__)
        _initialized = True

        logger.info(
            f"Observability initialized: service={service_name}, "
            f"namespace={service_namespace}, env={deployment_env}, "
            f"endpoint={endpoint}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to initialize observability: {e}")
        _init_noop()
        return False


def _init_noop():
    """Initialize no-op tracer/meter for when observability is disabled."""
    global _tracer, _meter, _initialized
    from opentelemetry import metrics, trace
    _tracer = trace.get_tracer(__name__)
    _meter = metrics.get_meter(__name__)
    _initialized = True


def get_tracer(name: str = __name__):
    """Get a tracer for creating spans."""
    if not _initialized:
        _init_noop()
    from opentelemetry import trace
    return trace.get_tracer(name)


def get_meter(name: str = __name__):
    """Get a meter for creating metrics."""
    if not _initialized:
        _init_noop()
    from opentelemetry import metrics
    return metrics.get_meter(name)


def is_enabled() -> bool:
    """Check if observability is enabled and configured."""
    return (
        os.environ.get("OTEL_ENABLED", "true").lower() in ("true", "1", "yes")
        and os.environ.get("GRAFANA_OTLP_ENDPOINT")
        and os.environ.get("GRAFANA_INSTANCE_ID")
        and os.environ.get("GRAFANA_API_KEY")
    )
