"""
Observability - OpenTelemetry traces and metrics.

Supports two modes:
1. Via Alloy/Collector: Set OTEL_EXPORTER_ENDPOINT to send to a local collector
2. Direct to Grafana Cloud: Set GRAFANA_* vars for direct export

Usage:
    from mypalclara.observability import init_observability, get_tracer, get_meter

    init_observability()

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my-operation"):
        pass

Environment Variables:
    OTEL_ENABLED: Enable observability (default: true)
    OTEL_EXPORTER_ENDPOINT: OTLP endpoint (e.g., http://alloy.railway.internal:4317)
    OTEL_SERVICE_NAME: Service name (default: clara-discord)
    OTEL_SERVICE_NAMESPACE: Namespace (default: mypalclara)
    OTEL_DEPLOYMENT_ENV: Environment (default: production)

    For direct Grafana Cloud export (if OTEL_EXPORTER_ENDPOINT not set):
    GRAFANA_OTLP_ENDPOINT: Grafana Cloud OTLP endpoint
    GRAFANA_INSTANCE_ID: Instance ID for auth
    GRAFANA_API_KEY: API key for auth
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
    Initialize OpenTelemetry with OTLP export.

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

    # Determine export mode
    otel_endpoint = os.environ.get("OTEL_EXPORTER_ENDPOINT")
    grafana_endpoint = os.environ.get("GRAFANA_OTLP_ENDPOINT")
    grafana_instance = os.environ.get("GRAFANA_INSTANCE_ID")
    grafana_key = os.environ.get("GRAFANA_API_KEY")

    if otel_endpoint:
        # Mode 1: Export to local collector (Alloy)
        return _init_with_collector(otel_endpoint)
    elif grafana_endpoint and grafana_instance and grafana_key:
        # Mode 2: Direct export to Grafana Cloud
        return _init_direct_grafana(grafana_endpoint, grafana_instance, grafana_key)
    else:
        logger.warning(
            "Observability not configured. Set OTEL_EXPORTER_ENDPOINT for Alloy, "
            "or GRAFANA_OTLP_ENDPOINT + GRAFANA_INSTANCE_ID + GRAFANA_API_KEY for direct export."
        )
        _init_noop()
        return False


def _init_with_collector(endpoint: str) -> bool:
    """Initialize with a local OTLP collector (Alloy)."""
    global _initialized, _tracer, _meter

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
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
        resource = _create_resource()

        # Traces via gRPC
        trace_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        trace_provider = TracerProvider(resource=resource)
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        trace.set_tracer_provider(trace_provider)

        # Metrics via gRPC
        metric_exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
        metric_reader = PeriodicExportingMetricReader(
            metric_exporter, export_interval_millis=60000
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)

        _tracer = trace.get_tracer(__name__)
        _meter = metrics.get_meter(__name__)
        _initialized = True

        service_name = os.environ.get("OTEL_SERVICE_NAME", "clara-discord")
        logger.info(f"Observability initialized via collector: {endpoint} (service={service_name})")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize observability: {e}")
        _init_noop()
        return False


def _init_direct_grafana(endpoint: str, instance_id: str, api_key: str) -> bool:
    """Initialize with direct export to Grafana Cloud."""
    global _initialized, _tracer, _meter

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
        resource = _create_resource()

        # Build auth header
        auth_string = f"{instance_id}:{api_key}"
        auth_bytes = base64.b64encode(auth_string.encode()).decode()
        headers = {"Authorization": f"Basic {auth_bytes}"}

        # Traces via HTTP
        trace_exporter = OTLPSpanExporter(
            endpoint=f"{endpoint}/v1/traces", headers=headers
        )
        trace_provider = TracerProvider(resource=resource)
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        trace.set_tracer_provider(trace_provider)

        # Metrics via HTTP
        metric_exporter = OTLPMetricExporter(
            endpoint=f"{endpoint}/v1/metrics", headers=headers
        )
        metric_reader = PeriodicExportingMetricReader(
            metric_exporter, export_interval_millis=60000
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)

        _tracer = trace.get_tracer(__name__)
        _meter = metrics.get_meter(__name__)
        _initialized = True

        service_name = os.environ.get("OTEL_SERVICE_NAME", "clara-discord")
        logger.info(f"Observability initialized direct to Grafana: {endpoint} (service={service_name})")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize observability: {e}")
        _init_noop()
        return False


def _create_resource():
    """Create OpenTelemetry resource with service attributes."""
    from opentelemetry.sdk.resources import Resource

    service_name = os.environ.get("OTEL_SERVICE_NAME", "clara-discord")
    service_namespace = os.environ.get("OTEL_SERVICE_NAMESPACE", "mypalclara")
    deployment_env = os.environ.get("OTEL_DEPLOYMENT_ENV", "production")

    return Resource.create({
        "service.name": service_name,
        "service.namespace": service_namespace,
        "deployment.environment": deployment_env,
        "service.version": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev")[:8],
    })


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
    if os.environ.get("OTEL_ENABLED", "true").lower() not in ("true", "1", "yes"):
        return False

    # Either collector or direct Grafana
    has_collector = bool(os.environ.get("OTEL_EXPORTER_ENDPOINT"))
    has_grafana = all([
        os.environ.get("GRAFANA_OTLP_ENDPOINT"),
        os.environ.get("GRAFANA_INSTANCE_ID"),
        os.environ.get("GRAFANA_API_KEY"),
    ])

    return has_collector or has_grafana
