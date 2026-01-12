"""
Metrics Server - Exposes Prometheus metrics from the Discord bot process.

This runs as a background thread in the same process as the bot,
so it has access to all the metrics that Cortex is tracking.

Usage:
    from mypalclara.metrics_server import start_metrics_server
    start_metrics_server(port=9090)
"""

import logging
import os
import threading
from http.server import HTTPServer

logger = logging.getLogger(__name__)

_server: HTTPServer | None = None
_thread: threading.Thread | None = None


def start_metrics_server(port: int = 9090, addr: str = "0.0.0.0") -> bool:
    """
    Start the Prometheus metrics HTTP server in a background thread.

    Args:
        port: Port to listen on (default: 9090)
        addr: Address to bind to (default: 0.0.0.0)

    Returns:
        True if server started, False if prometheus_client not available
    """
    global _server, _thread

    try:
        from prometheus_client import start_http_server, REGISTRY
        from prometheus_client.exposition import MetricsHandler
    except ImportError:
        logger.warning(
            "prometheus_client not installed, metrics server disabled. "
            "Install with: poetry add prometheus_client"
        )
        return False

    if _server is not None:
        logger.warning("Metrics server already running")
        return True

    try:
        # Start the prometheus HTTP server
        # This runs in a daemon thread
        start_http_server(port, addr=addr)
        logger.info(f"Metrics server started on http://{addr}:{port}/metrics")
        return True
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        return False


def get_metrics_port() -> int:
    """Get the configured metrics port from environment."""
    return int(os.environ.get("METRICS_PORT", "9090"))


def is_metrics_enabled() -> bool:
    """Check if metrics are enabled via environment."""
    return os.environ.get("METRICS_ENABLED", "true").lower() in ("true", "1", "yes")
