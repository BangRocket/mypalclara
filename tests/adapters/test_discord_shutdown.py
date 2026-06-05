"""Shutdown-coordination tests for the Discord adapter.

Regression guard for the bug where ``main()`` ran the bot via
``asyncio.gather(bot.start(), stop_event.wait())``. ``gather`` only returns once
*both* awaitables finish, but ``bot.start()`` runs forever, so setting
``stop_event`` on SIGINT/SIGTERM never ended the gather and the bot never closed.
The fix lives in ``discord/main.py::_run_until_stopped``.
"""

from __future__ import annotations

import asyncio

import pytest

from mypalclara.adapters.discord.main import _run_until_stopped


class _ForeverBot:
    """Stand-in for the discord client whose ``start()`` never returns."""

    def __init__(self) -> None:
        self.started = False

    async def start(self, token: str) -> None:
        self.started = True
        await asyncio.Event().wait()  # blocks forever, like a live bot


async def test_stop_event_ends_run_even_though_bot_runs_forever() -> None:
    bot = _ForeverBot()
    stop_event = asyncio.Event()

    async def fire_signal() -> None:
        await asyncio.sleep(0.05)  # let the bot task start first
        stop_event.set()

    # Must return promptly once stop_event is set. Times out (fails) if the old
    # gather-both behavior ever comes back.
    await asyncio.wait_for(
        asyncio.gather(
            _run_until_stopped(bot, "fake-token", stop_event),
            fire_signal(),
        ),
        timeout=2.0,
    )
    assert bot.started


async def test_bot_start_failure_propagates() -> None:
    class _FailingBot:
        async def start(self, token: str) -> None:
            raise RuntimeError("bad token")

    stop_event = asyncio.Event()
    # A crash inside bot.start() must surface (so main() logs it), not hang.
    with pytest.raises(RuntimeError, match="bad token"):
        await asyncio.wait_for(
            _run_until_stopped(_FailingBot(), "fake-token", stop_event),
            timeout=2.0,
        )
