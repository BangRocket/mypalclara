"""
Observability - OpenTelemetry traces, metrics, and logs via Axiom.

Usage:
    from mypalclara.observability import init_observability, get_tracer, get_meter

    init_observability()

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my-operation"):
        pass

Environment Variables:
    AXIOM_TOKEN: Axiom API token (required)
    AXIOM_DATASET: Dataset name (default: clara)
    OTEL_ENABLED: Enable observability (default: true)
    OTEL_SERVICE_NAME: Service name (default: clara-discord)
    OTEL_LOG_LEVEL: Minimum log level to export (default: INFO)
"""

import logging
import os

logger = logging.getLogger(__name__)

_initialized = False
_noop_initialized = False
_tracer = None
_meter = None

# Axiom OTLP endpoints
AXIOM_OTLP_TRACES = "https://api.axiom.co/v1/traces"
AXIOM_OTLP_LOGS = "https://api.axiom.co/v1/logs"
AXIOM_OTLP_METRICS = "https://api.axiom.co/v1/metrics"


def init_observability() -> bool:
    """
    Initialize OpenTelemetry with Axiom export.

    Returns:
        True if initialized successfully, False otherwise
    """
    global _initialized, _noop_initialized, _tracer, _meter

    print("[observability] init_observability() called", flush=True)

    if _initialized and not _noop_initialized:
        print("[observability] Already initialized, returning True", flush=True)
        return True

    if _noop_initialized:
        print("[observability] Upgrading from noop to real exporters...", flush=True)

    # Check if enabled
    if os.environ.get("OTEL_ENABLED", "true").lower() not in ("true", "1", "yes"):
        print("[observability] Disabled via OTEL_ENABLED=false", flush=True)
        _init_noop()
        return False

    # Check for Axiom token
    axiom_token = os.environ.get("AXIOM_TOKEN")
    if not axiom_token:
        print("[observability] AXIOM_TOKEN not set, using noop", flush=True)
        _init_noop()
        return False

    axiom_dataset = os.environ.get("AXIOM_DATASET", "clara")
    print(f"[observability] Initializing Axiom export (dataset={axiom_dataset})", flush=True)

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as e:
        print(f"[observability] OpenTelemetry packages not installed: {e}", flush=True)
        _init_noop()
        return False

    try:
        # Build headers for Axiom (metrics need different header)
        base_headers = {
            "Authorization": f"Bearer {axiom_token}",
            "X-Axiom-Dataset": axiom_dataset,
        }
        metrics_headers = {
            "Authorization": f"Bearer {axiom_token}",
            "X-Axiom-Metrics-Dataset": axiom_dataset,
        }

        # Create resource
        service_name = os.environ.get("OTEL_SERVICE_NAME", "clara-discord")
        resource = Resource.create({
            "service.name": service_name,
            "service.namespace": "mypalclara",
            "deployment.environment": os.environ.get("RAILWAY_ENVIRONMENT", "development"),
            "service.version": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "dev")[:8],
        })

        # Traces
        trace_exporter = OTLPSpanExporter(endpoint=AXIOM_OTLP_TRACES, headers=base_headers)
        trace_provider = TracerProvider(resource=resource)
        trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        trace.set_tracer_provider(trace_provider)
        print("[observability] Trace exporter configured", flush=True)

        # Metrics (uses different header)
        metric_exporter = OTLPMetricExporter(endpoint=AXIOM_OTLP_METRICS, headers=metrics_headers)
        metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60000)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)
        print("[observability] Metric exporter configured", flush=True)

        # Logs
        try:
            from opentelemetry._logs import set_logger_provider
            from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
            from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
            from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

            log_exporter = OTLPLogExporter(endpoint=AXIOM_OTLP_LOGS, headers=base_headers)
            logger_provider = LoggerProvider(resource=resource)
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
            set_logger_provider(logger_provider)

            log_level = getattr(logging, os.environ.get("OTEL_LOG_LEVEL", "INFO").upper(), logging.INFO)
            otel_handler = LoggingHandler(level=log_level, logger_provider=logger_provider)
            logging.getLogger().addHandler(otel_handler)
            print(f"[observability] Log exporter configured (level={logging.getLevelName(log_level)})", flush=True)
        except ImportError as e:
            print(f"[observability] Log exporter not available: {e}", flush=True)

        _tracer = trace.get_tracer(__name__)
        _meter = metrics.get_meter(__name__)
        _initialized = True
        _noop_initialized = False

        print(f"[observability] ✓ Axiom initialized (service={service_name}, dataset={axiom_dataset})", flush=True)
        return True

    except Exception as e:
        print(f"[observability] Failed to initialize: {e}", flush=True)
        import traceback
        traceback.print_exc()
        _init_noop()
        return False


def _init_noop():
    """Initialize no-op tracer/meter."""
    global _tracer, _meter, _initialized, _noop_initialized
    from opentelemetry import metrics, trace
    _tracer = trace.get_tracer(__name__)
    _meter = metrics.get_meter(__name__)
    _initialized = True
    _noop_initialized = True


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
    return bool(os.environ.get("AXIOM_TOKEN"))
