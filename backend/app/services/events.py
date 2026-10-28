"""In-process incident event hub for Server-Sent Events."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any


class EventHub:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[str]] = []
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish_sync(self, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, default=str)
        loop = self._loop
        if loop is None or not loop.is_running():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
        loop.call_soon_threadsafe(self._broadcast, message)

    def _broadcast(self, message: str) -> None:
        for queue in list(self._subscribers):
            if queue.full():
                continue
            queue.put_nowait(message)

    async def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=64)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def stream(self) -> AsyncIterator[str]:
        queue = await self.subscribe()
        try:
            yield "event: ping\ndata: {}\n\n"
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"event: incident\ndata: {message}\n\n"
                except TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            self.unsubscribe(queue)


hub = EventHub()
