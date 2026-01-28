"""Token bucket rate limiter for the Clara Gateway.

Implements rate limiting per channel/user combination to prevent abuse.
Uses the token bucket algorithm for smooth rate limiting with burst capacity.

Token Bucket Algorithm:
- Each bucket starts with `capacity` tokens
- Tokens refill at `rate` tokens per second (up to capacity)
- Each request consumes 1 token
- If no tokens available, request is rejected with retry-after timing

Configuration via environment variables:
- RATE_LIMIT_BURST: Maximum burst capacity (default: 10)
- RATE_LIMIT_PER_SEC: Sustained rate in requests/second (default: 2.0)
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Token bucket for rate limiting.

    Attributes:
        capacity: Maximum tokens the bucket can hold (burst limit)
        rate: Token refill rate per second (sustained rate)
        tokens: Current number of tokens
        last_update: Monotonic timestamp of last update
    """

    capacity: int = 10
    rate: float = 2.0
    tokens: float = field(default=None)  # type: ignore
    last_update: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        """Initialize tokens to capacity if not set."""
        if self.tokens is None:
            self.tokens = float(self.capacity)

    def consume(self, tokens: int = 1) -> bool:
        """Attempt to consume tokens from the bucket.

        First refills the bucket based on elapsed time, then attempts
        to consume the requested tokens.

        Args:
            tokens: Number of tokens to consume (default: 1)

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens based on elapsed time (up to capacity)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_until_available(self, tokens: int = 1) -> float:
        """Calculate time until requested tokens will be available.

        Args:
            tokens: Number of tokens needed

        Returns:
            Seconds until tokens available (0 if already available)
        """
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.rate


class RateLimiter:
    """Rate limiter using token buckets per channel/user.

    Creates a separate bucket for each unique channel_id:user_id combination.
    Buckets are automatically created on first access and cleaned up
    periodically to prevent memory growth.

    Example:
        limiter = RateLimiter(capacity=10, rate=2.0)
        allowed, retry_after = await limiter.check_rate_limit("ch1", "user1")
        if not allowed:
            return f"Rate limited. Retry in {retry_after:.1f}s"
    """

    def __init__(
        self,
        capacity: int | None = None,
        rate: float | None = None,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            capacity: Burst capacity (max tokens). Default from RATE_LIMIT_BURST env or 10.
            rate: Sustained rate (tokens/sec). Default from RATE_LIMIT_PER_SEC env or 2.0.
        """
        self.capacity = capacity or int(os.getenv("RATE_LIMIT_BURST", "10"))
        self.rate = rate or float(os.getenv("RATE_LIMIT_PER_SEC", "2.0"))
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        channel_id: str,
        user_id: str,
    ) -> tuple[bool, float]:
        """Check if a request should be allowed.

        Args:
            channel_id: Channel identifier
            user_id: User identifier

        Returns:
            Tuple of (allowed: bool, retry_after: float).
            If allowed is False, retry_after indicates seconds until retry.
        """
        key = f"{channel_id}:{user_id}"

        async with self._lock:
            # Get or create bucket for this key
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(
                    capacity=self.capacity,
                    rate=self.rate,
                )

            bucket = self._buckets[key]

            if bucket.consume(1):
                return (True, 0.0)
            else:
                retry_after = bucket.time_until_available(1)
                return (False, retry_after)

    async def cleanup_stale(self, max_age_seconds: int = 3600) -> int:
        """Remove buckets that haven't been accessed recently.

        Buckets that have been idle (no consume attempts) for longer
        than max_age_seconds are removed to prevent memory growth.

        Args:
            max_age_seconds: Maximum idle time before cleanup (default: 1 hour)

        Returns:
            Number of buckets removed
        """
        now = time.monotonic()
        removed = 0

        async with self._lock:
            # Find stale buckets
            stale_keys = [
                key
                for key, bucket in self._buckets.items()
                if (now - bucket.last_update) > max_age_seconds
            ]

            # Remove them
            for key in stale_keys:
                del self._buckets[key]
                removed += 1

        return removed

    async def get_bucket_count(self) -> int:
        """Get the number of active buckets (for monitoring)."""
        async with self._lock:
            return len(self._buckets)
