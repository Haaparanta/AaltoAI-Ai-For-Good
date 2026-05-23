"""Run blocking work without blocking the UI event loop."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


async def run_sync_daemon(func: Callable[..., T], /, *args, **kwargs) -> T:
    """Run a sync callable on a daemon thread and await its result."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[T] = loop.create_future()

    def worker() -> None:
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            loop.call_soon_threadsafe(future.set_exception, exc)
        else:
            loop.call_soon_threadsafe(future.set_result, result)

    threading.Thread(
        target=worker,
        name=f"sync-daemon:{getattr(func, '__name__', 'worker')}",
        daemon=True,
    ).start()
    return await future
