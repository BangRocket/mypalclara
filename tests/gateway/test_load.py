"""Load testing script for the Clara Gateway.

Tests gateway capacity under concurrent WebSocket connections.

Usage:
    poetry run python tests/gateway/test_load.py --help
    poetry run python tests/gateway/test_load.py --clients 20 --duration 30
    poetry run python tests/gateway/test_load.py --clients 100 --duration 60 --ramp-up 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed


@dataclass
class LoadTestResult:
    """Result from a single client's load test run."""

    client_id: str
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    connected: bool = False
    connection_time_ms: float = 0.0
    error_messages: list[str] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        """Average latency in milliseconds."""
        if not self.latencies_ms:
            return 0.0
        return statistics.mean(self.latencies_ms)

    @property
    def success_rate(self) -> float:
        """Percentage of successful message exchanges."""
        total = self.messages_sent
        if total == 0:
            return 0.0
        return ((total - self.errors) / total) * 100


@dataclass
class AggregateResult:
    """Aggregate results from all load test clients."""

    total_clients: int
    successful_connections: int
    total_messages_sent: int
    total_messages_received: int
    total_errors: int
    all_latencies_ms: list[float]
    duration_seconds: float
    connection_times_ms: list[float]
    error_messages: list[str]

    @property
    def p50_latency_ms(self) -> float:
        """50th percentile latency."""
        if not self.all_latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.all_latencies_ms)
        idx = int(len(sorted_latencies) * 0.50)
        return sorted_latencies[idx] if sorted_latencies else 0.0

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency."""
        if not self.all_latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.all_latencies_ms)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def p99_latency_ms(self) -> float:
        """99th percentile latency."""
        if not self.all_latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.all_latencies_ms)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    @property
    def avg_latency_ms(self) -> float:
        """Average latency."""
        if not self.all_latencies_ms:
            return 0.0
        return statistics.mean(self.all_latencies_ms)

    @property
    def throughput(self) -> float:
        """Messages per second."""
        if self.duration_seconds == 0:
            return 0.0
        return self.total_messages_sent / self.duration_seconds

    @property
    def error_rate(self) -> float:
        """Percentage of errors."""
        if self.total_messages_sent == 0:
            return 0.0
        return (self.total_errors / self.total_messages_sent) * 100

    @property
    def connection_success_rate(self) -> float:
        """Percentage of successful connections."""
        if self.total_clients == 0:
            return 0.0
        return (self.successful_connections / self.total_clients) * 100

    def summary(self) -> str:
        """Generate human-readable summary of results."""
        lines = [
            "",
            "=" * 60,
            "LOAD TEST RESULTS",
            "=" * 60,
            "",
            f"Duration: {self.duration_seconds:.1f}s",
            f"Clients: {self.successful_connections}/{self.total_clients} connected ({self.connection_success_rate:.1f}%)",
            "",
            "MESSAGE STATISTICS:",
            f"  Sent: {self.total_messages_sent}",
            f"  Received: {self.total_messages_received}",
            f"  Errors: {self.total_errors} ({self.error_rate:.1f}%)",
            f"  Throughput: {self.throughput:.1f} msg/s",
            "",
            "LATENCY (ms):",
            f"  Average: {self.avg_latency_ms:.1f}",
            f"  p50: {self.p50_latency_ms:.1f}",
            f"  p95: {self.p95_latency_ms:.1f}",
            f"  p99: {self.p99_latency_ms:.1f}",
            "",
        ]

        if self.connection_times_ms:
            avg_conn = statistics.mean(self.connection_times_ms)
            lines.append(f"CONNECTION TIME: {avg_conn:.1f}ms avg")
            lines.append("")

        # Pass/fail assessment
        lines.append("ASSESSMENT:")
        passed = True

        if self.connection_success_rate < 95:
            lines.append(f"  [FAIL] Connection rate {self.connection_success_rate:.1f}% < 95%")
            passed = False
        else:
            lines.append(f"  [PASS] Connection rate {self.connection_success_rate:.1f}% >= 95%")

        if self.error_rate > 5:
            lines.append(f"  [FAIL] Error rate {self.error_rate:.1f}% > 5%")
            passed = False
        else:
            lines.append(f"  [PASS] Error rate {self.error_rate:.1f}% <= 5%")

        if self.p95_latency_ms > 5000:
            lines.append(f"  [FAIL] p95 latency {self.p95_latency_ms:.1f}ms > 5000ms")
            passed = False
        else:
            lines.append(f"  [PASS] p95 latency {self.p95_latency_ms:.1f}ms <= 5000ms")

        lines.append("")
        lines.append("=" * 60)
        lines.append(f"OVERALL: {'PASS' if passed else 'FAIL'}")
        lines.append("=" * 60)

        if self.error_messages:
            lines.append("")
            lines.append("SAMPLE ERRORS (first 5):")
            for msg in self.error_messages[:5]:
                lines.append(f"  - {msg}")

        return "\n".join(lines)


async def simulate_client(
    client_id: str,
    host: str,
    port: int,
    duration_seconds: int,
    message_interval: float = 1.0,
    start_delay: float = 0.0,
) -> LoadTestResult:
    """Simulate a single WebSocket client.

    Args:
        client_id: Unique identifier for this client
        host: Gateway host
        port: Gateway port
        duration_seconds: How long to run the test
        message_interval: Time between messages in seconds
        start_delay: Delay before starting (for ramp-up)

    Returns:
        LoadTestResult with this client's statistics
    """
    result = LoadTestResult(client_id=client_id)

    # Apply ramp-up delay
    if start_delay > 0:
        await asyncio.sleep(start_delay)

    uri = f"ws://{host}:{port}"
    conn_start = time.perf_counter()

    try:
        async with websockets.connect(
            uri,
            ping_interval=30,
            ping_timeout=10,
            close_timeout=5,
        ) as ws:
            conn_end = time.perf_counter()
            result.connection_time_ms = (conn_end - conn_start) * 1000
            result.connected = True

            # Register as a load test adapter
            register_msg = {
                "type": "register",
                "node_id": f"loadtest-{client_id}",
                "platform": "loadtest",
                "capabilities": ["text"],
                "metadata": {"load_test": True},
            }
            await ws.send(json.dumps(register_msg))

            # Wait for registration response
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(response)
                if data.get("type") != "registered":
                    result.errors += 1
                    result.error_messages.append(f"Registration failed: {data}")
                    return result
            except asyncio.TimeoutError:
                result.errors += 1
                result.error_messages.append("Registration timeout")
                return result

            # Send messages for the duration
            end_time = asyncio.get_event_loop().time() + duration_seconds
            message_num = 0

            while asyncio.get_event_loop().time() < end_time:
                message_num += 1
                request_id = f"{client_id}-{message_num}"

                # Create a message request
                msg_request = {
                    "type": "message",
                    "id": request_id,
                    "content": f"Load test message {message_num} from {client_id}",
                    "user": {
                        "id": f"user-{client_id}",
                        "name": f"LoadTester-{client_id}",
                        "platform_id": f"loadtest-{client_id}",
                    },
                    "channel": {
                        "id": f"channel-{client_id}",
                        "type": "dm",
                        "name": f"LoadTest-{client_id}",
                    },
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {"load_test": True},
                }

                send_time = time.perf_counter()
                result.messages_sent += 1

                try:
                    await ws.send(json.dumps(msg_request))

                    # Wait for response (with timeout)
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=30.0)
                        recv_time = time.perf_counter()
                        latency_ms = (recv_time - send_time) * 1000
                        result.latencies_ms.append(latency_ms)
                        result.messages_received += 1

                        # Parse response
                        data = json.loads(response)
                        if data.get("type") == "error":
                            result.errors += 1
                            result.error_messages.append(
                                f"Error response: {data.get('code')} - {data.get('message')}"
                            )

                    except asyncio.TimeoutError:
                        result.errors += 1
                        result.error_messages.append(f"Response timeout for message {message_num}")

                except ConnectionClosed as e:
                    result.errors += 1
                    result.error_messages.append(f"Connection closed: {e}")
                    break

                except Exception as e:
                    result.errors += 1
                    result.error_messages.append(f"Send error: {e}")

                # Wait before next message
                await asyncio.sleep(message_interval)

    except ConnectionClosed as e:
        result.error_messages.append(f"Connection closed during setup: {e}")
    except Exception as e:
        result.error_messages.append(f"Connection failed: {e}")

    return result


async def run_load_test(
    num_clients: int,
    duration_seconds: int,
    host: str = "127.0.0.1",
    port: int = 18789,
    ramp_up_seconds: float = 0.0,
    message_interval: float = 1.0,
) -> AggregateResult:
    """Run a load test with multiple concurrent clients.

    Args:
        num_clients: Number of concurrent WebSocket clients
        duration_seconds: Duration of the test in seconds
        host: Gateway host address
        port: Gateway port
        ramp_up_seconds: Time to gradually start all clients
        message_interval: Time between messages per client

    Returns:
        AggregateResult with combined statistics from all clients
    """
    print(f"\nStarting load test:")
    print(f"  Clients: {num_clients}")
    print(f"  Duration: {duration_seconds}s")
    print(f"  Target: ws://{host}:{port}")
    print(f"  Ramp-up: {ramp_up_seconds}s")
    print(f"  Message interval: {message_interval}s")
    print()

    start_time = time.perf_counter()

    # Calculate ramp-up delay per client
    ramp_delay = ramp_up_seconds / num_clients if ramp_up_seconds > 0 else 0

    # Create client tasks
    tasks = []
    for i in range(num_clients):
        client_id = f"client-{i:04d}"
        delay = i * ramp_delay
        task = asyncio.create_task(
            simulate_client(
                client_id=client_id,
                host=host,
                port=port,
                duration_seconds=duration_seconds,
                message_interval=message_interval,
                start_delay=delay,
            )
        )
        tasks.append(task)

    # Wait for all clients to complete
    results: list[LoadTestResult] = await asyncio.gather(*tasks)

    end_time = time.perf_counter()
    actual_duration = end_time - start_time

    # Aggregate results
    all_latencies: list[float] = []
    all_conn_times: list[float] = []
    all_errors: list[str] = []
    total_sent = 0
    total_received = 0
    total_errors = 0
    successful_connections = 0

    for r in results:
        all_latencies.extend(r.latencies_ms)
        if r.connection_time_ms > 0:
            all_conn_times.append(r.connection_time_ms)
        all_errors.extend(r.error_messages)
        total_sent += r.messages_sent
        total_received += r.messages_received
        total_errors += r.errors
        if r.connected:
            successful_connections += 1

    return AggregateResult(
        total_clients=num_clients,
        successful_connections=successful_connections,
        total_messages_sent=total_sent,
        total_messages_received=total_received,
        total_errors=total_errors,
        all_latencies_ms=all_latencies,
        duration_seconds=actual_duration,
        connection_times_ms=all_conn_times,
        error_messages=all_errors,
    )


def main() -> None:
    """Main entry point for load testing."""
    parser = argparse.ArgumentParser(
        description="Load test the Clara Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test with 10 clients
  python tests/gateway/test_load.py --clients 10 --duration 30

  # Full load test with 100 clients
  python tests/gateway/test_load.py --clients 100 --duration 60

  # Gradual ramp-up over 10 seconds
  python tests/gateway/test_load.py --clients 50 --duration 60 --ramp-up 10

  # Custom host/port
  python tests/gateway/test_load.py --host 192.168.1.100 --port 8080 --clients 20
        """,
    )
    parser.add_argument(
        "--clients",
        type=int,
        default=10,
        help="Number of concurrent clients (default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Test duration in seconds (default: 30)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Gateway host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=18789,
        help="Gateway port (default: 18789)",
    )
    parser.add_argument(
        "--ramp-up",
        type=float,
        default=0.0,
        help="Ramp-up time in seconds (default: 0, all clients start immediately)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Message interval per client in seconds (default: 1.0)",
    )

    args = parser.parse_args()

    # Run the load test
    result = asyncio.run(
        run_load_test(
            num_clients=args.clients,
            duration_seconds=args.duration,
            host=args.host,
            port=args.port,
            ramp_up_seconds=args.ramp_up,
            message_interval=args.interval,
        )
    )

    # Print summary
    print(result.summary())

    # Exit with appropriate code
    if result.error_rate > 5 or result.p95_latency_ms > 5000:
        exit(1)
    exit(0)


if __name__ == "__main__":
    main()
