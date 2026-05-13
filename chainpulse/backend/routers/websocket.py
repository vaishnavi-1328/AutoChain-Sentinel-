"""WS /ws/events?token=<jwt>. JWT optional — if absent, subscribes to global channel."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from chainpulse.backend.db.postgres import get_session
from chainpulse.backend.services.auth_deps import ws_user_from_token
from chainpulse.backend.services.connection_manager import GLOBAL_CHANNEL, USER_CHANNEL_PREFIX, manager

router = APIRouter(tags=["websocket"])
log = logging.getLogger("chainpulse.ws.router")


@router.websocket("/ws/events")
async def ws_events(
    websocket: WebSocket,
    token: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> None:
    user_id: str | None = None
    if token:
        try:
            user = await ws_user_from_token(token, session)
            user_id = str(user.id)
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    channel_key = user_id or f"anon:{uuid.uuid4().hex[:12]}"
    channels = [GLOBAL_CHANNEL]
    if user_id:
        channels.append(USER_CHANNEL_PREFIX + user_id)

    await manager.connect(websocket, channel_key, channels)
    try:
        while True:
            # discard any client→server frames (dashboard is read-only)
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(channel_key)
