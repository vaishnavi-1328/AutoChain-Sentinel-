"""WebSocket ConnectionManager — per-user registry + Redis pub/sub fan-out."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from chainpulse.backend.db.redis import get_redis

log = logging.getLogger("chainpulse.ws.manager")

USER_CHANNEL_PREFIX = "events:"
GLOBAL_CHANNEL = "events:*"


class ConnectionManager:
    def __init__(self) -> None:
        # key: user_id (str) or anon connection uuid; value: WebSocket
        self._connections: dict[str, WebSocket] = {}
        self._subs: dict[str, asyncio.Task] = {}

    async def connect(self, ws: WebSocket, channel_key: str, subscribe_channels: list[str]) -> None:
        await ws.accept()
        self._connections[channel_key] = ws
        # Spawn a subscriber task for this connection that forwards Redis pub messages.
        task = asyncio.create_task(self._pump(channel_key, subscribe_channels))
        self._subs[channel_key] = task
        log.info("ws connect %s channels=%s", channel_key, subscribe_channels)

    async def _pump(self, channel_key: str, channels: list[str]) -> None:
        r = get_redis()
        pubsub = r.pubsub()
        try:
            await pubsub.subscribe(*channels)
            async for msg in pubsub.listen():
                if msg["type"] != "message":
                    continue
                ws = self._connections.get(channel_key)
                if ws is None:
                    break
                try:
                    payload: Any = msg["data"]
                    if isinstance(payload, (bytes, bytearray)):
                        payload = payload.decode("utf-8", errors="ignore")
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except Exception:
                            pass
                    await ws.send_json(payload)
                except WebSocketDisconnect:
                    break
                except Exception:
                    log.exception("ws send failed for %s", channel_key)
                    break
        finally:
            try:
                await pubsub.unsubscribe(*channels)
            except Exception:
                pass
            try:
                await pubsub.close()
            except Exception:
                pass

    async def disconnect(self, channel_key: str) -> None:
        ws = self._connections.pop(channel_key, None)
        task = self._subs.pop(channel_key, None)
        if task:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        log.info("ws disconnect %s", channel_key)


manager = ConnectionManager()
