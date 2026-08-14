"""FastAPI router for real-time WebSocket connections (``16-realtime-architecture.md``)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from lpg.api.app import get_app_state
from lpg.application.common.errors import TokenInvalidError
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.application.identity.ports import JwtSigner
    from lpg.infrastructure.realtime.connection_manager import ConnectionManager

_logger = get_logger(__name__)
router = APIRouter(tags=["Realtime"])

# Ping interval to detect dead connections
_PING_INTERVAL_S = 30.0


async def _verify_token(token: str, signer: JwtSigner) -> dict[str, Any]:
    """Verify JWT and return claims."""
    return signer.decode_access_token(token)


def _resolve_subscription_intent(
    intent: str, claims: dict[str, Any]
) -> str | None:
    """Map a client's subscription intent to a server-constructed Redis channel.

    Enforces RBAC on the subscription intent exactly as REST endpoints do (D-38).
    Returns the channel string if authorized, or None if denied/invalid.
    """
    tenant_id = claims.get("tenant_id")
    user_id = claims.get("sub")
    permissions: list[str] = claims.get("scope", "").split()
    role = claims.get("role")

    if not tenant_id or not user_id:
        return None

    if intent == "dashboard":
        if "reports:read" in permissions:
            return f"tenant:{tenant_id}:dashboard"
        return None

    if intent == "notifications":
        return f"tenant:{tenant_id}:user:{user_id}"

    if intent == "dispatch":
        if "orders:read" in permissions or "routes:read" in permissions:
            return f"tenant:{tenant_id}:dispatch"
        return None

    if intent == "driver":
        if role == "driver":
            return f"tenant:{tenant_id}:driver:{user_id}"
        return None

    if intent.startswith("order:"):
        try:
            _, order_id_str = intent.split(":", 1)
            uuid.UUID(order_id_str)
            if "orders:read" in permissions or role == "customer":
                return f"tenant:{tenant_id}:order:{order_id_str}"
        except ValueError:
            pass
        return None

    return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, token: str = Query(...)
) -> None:
    """Accept a WebSocket connection and handle real-time subscriptions."""
    state = get_app_state()
    signer = state.jwt_signer
    manager = state.connection_manager

    if signer is None or manager is None:
        await websocket.close(code=1011)
        return

    try:
        claims = await _verify_token(token, signer)
    except TokenInvalidError:
        await websocket.close(code=1008)  # Policy Violation
        return

    await websocket.accept()
    
    # We maintain the active channels for this socket to handle refresh and cleanup
    active_channels: list[str] = []

    try:
        while True:
            # We use wait_for to enforce keepalive/ping
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=_PING_INTERVAL_S)
            except asyncio.TimeoutError:
                # Send ping
                try:
                    await websocket.send_json({"type": "ping"})
                    continue
                except Exception:
                    break

            try:
                data = json.loads(message)
            except ValueError:
                continue
                
            if data.get("type") == "pong":
                continue

            # Token refresh handling
            if "refresh_token" in data:
                try:
                    claims = await _verify_token(data["refresh_token"], signer)
                except TokenInvalidError:
                    await websocket.close(code=1008)
                    return
                continue
                
            # Subscription handling
            if "subscribe" in data and isinstance(data["subscribe"], list):
                new_channels = []
                for intent in data["subscribe"]:
                    channel = _resolve_subscription_intent(intent, claims)
                    if channel and channel not in active_channels:
                        new_channels.append(channel)
                
                if new_channels:
                    active_channels.extend(new_channels)
                    await manager.connect(websocket, new_channels)
                    
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
