"""FastAPI router for real-time WebSocket connections (``16-realtime-architecture.md``).

**Authentication is the first message, not the URL.** A client opens
``/api/v1/ws`` with no credentials and sends ``{"type": "auth", "token":
"<access token>"}`` as its first frame; the server answers
``{"type": "ready"}`` and only then honours subscriptions. A token in the
query string ends up in every access log, proxy log and browser history on
the way (DO-38 / CA-18); a frame inside the TLS stream does not.

``?token=`` is still accepted for app builds installed before this change
— a transition period only; remove it once those builds are retired. The
access-log filter (``lpg.config.logging``) redacts it either way.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from lpg.api.v1.dependencies.realtime import build_subscription_ownership
from lpg.application.common.errors import TokenInvalidError
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.api.v1.dependencies.realtime import SubscriptionOwnership
    from lpg.application.identity.ports import JwtSigner

_logger = get_logger(__name__)
router = APIRouter(tags=["Realtime"])

# Ping interval to detect dead connections
_PING_INTERVAL_S = 30.0
# How long an unauthenticated socket may stay open waiting for its auth frame.
_AUTH_TIMEOUT_S = 10.0

#: Close code for a missing, invalid or expired token. Clients answer it by
#: refreshing their token, not by retrying with the same one.
_CLOSE_POLICY_VIOLATION = 1008

#: Roles that use the mobile apps — never given the tenant-wide feeds,
#: even though they hold `orders:read` for their own orders.
_APP_ROLES = frozenset({"customer", "driver"})


async def _verify_token(token: str, signer: JwtSigner) -> dict[str, Any]:
    """Verify JWT and return claims."""
    return signer.decode_access_token(token)


async def _resolve_subscription_intent(
    intent: str,
    claims: dict[str, Any],
    ownership: SubscriptionOwnership | None = None,
) -> str | None:
    """Map a client's subscription intent to a server-constructed Redis channel.

    Enforces RBAC on the subscription intent exactly as REST endpoints do (D-38).
    Returns the channel string if authorized, or None if denied/invalid.
    """
    tenant_id = claims.get("tenant_id")
    user_id = claims.get("sub")
    permissions: list[str] = str(claims.get("scope", "")).split()
    role = claims.get("role")
    is_staff = role not in _APP_ROLES

    if not tenant_id or not user_id:
        return None

    if intent == "dashboard":
        if is_staff and "reports:read" in permissions:
            return f"tenant:{tenant_id}:dashboard"
        return None

    if intent == "notifications":
        return f"tenant:{tenant_id}:user:{user_id}"

    if intent == "orders":
        # Tenant-wide order-status feed for the office's list screens. A
        # customer holds `orders:read` for their own orders only, so they
        # subscribe per order instead.
        if is_staff and "orders:read" in permissions:
            return f"tenant:{tenant_id}:orders"
        return None

    if intent == "dispatch":
        if is_staff and ("orders:read" in permissions or "routes:read" in permissions):
            return f"tenant:{tenant_id}:dispatch"
        return None

    if intent == "driver":
        # Route events are published per `Driver` record
        # (`tenant:{t}:driver:{driver.id}`), not per login.
        if role != "driver" or ownership is None:
            return None
        driver_id = await ownership.driver_id_for(uuid.UUID(tenant_id), uuid.UUID(user_id))
        return f"tenant:{tenant_id}:driver:{driver_id}" if driver_id else None

    if intent.startswith("order:"):
        _, order_id_str = intent.split(":", 1)
        try:
            order_id = uuid.UUID(order_id_str)
        except ValueError:
            return None
        channel = f"tenant:{tenant_id}:order:{order_id}"
        if is_staff and "orders:read" in permissions:
            return channel
        if role == "customer" and ownership is not None:
            owns = await ownership.customer_owns_order(
                uuid.UUID(tenant_id), uuid.UUID(user_id), order_id
            )
            return channel if owns else None
        return None

    return None


async def _authenticate(websocket: WebSocket, signer: JwtSigner) -> dict[str, Any] | None:
    """Claims from the first frame (or the legacy query token), or None."""
    legacy_token = websocket.query_params.get("token")
    if legacy_token:
        _logger.info("ws_legacy_query_token_used")
        try:
            return await _verify_token(legacy_token, signer)
        except TokenInvalidError:
            return None

    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=_AUTH_TIMEOUT_S)
        data = json.loads(raw)
    except (TimeoutError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("type") != "auth":
        return None
    token = data.get("token")
    if not isinstance(token, str) or not token:
        return None
    try:
        return await _verify_token(token, signer)
    except TokenInvalidError:
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Accept a WebSocket connection and handle real-time subscriptions."""
    from lpg.api.app import get_app_state

    state = get_app_state()
    signer = state.jwt_signer
    manager = state.connection_manager

    if signer is None or manager is None:
        await websocket.close(code=1011)
        return

    # Accept first: a close code is part of the WebSocket framing, which
    # only exists once the handshake has completed — closing before
    # `accept()` makes the browser report a generic 1006 instead of 1008.
    await websocket.accept()
    claims = await _authenticate(websocket, signer)
    if claims is None:
        await websocket.close(code=_CLOSE_POLICY_VIOLATION)
        return
    await websocket.send_json({"type": "ready"})

    ownership = build_subscription_ownership(state.database)
    active_channels: list[str] = []

    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=_PING_INTERVAL_S)
            except TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                    continue
                except Exception:  # noqa: BLE001 - send failure means the socket is gone, break
                    break

            try:
                data = json.loads(message)
            except ValueError:
                continue
            if not isinstance(data, dict) or data.get("type") == "pong":
                continue

            # A fresh access token for this socket — must be the same user
            # in the same tenant, or the socket would silently change hands.
            new_token = data.get("refresh_token") or (
                data.get("token") if data.get("type") == "auth" else None
            )
            if new_token:
                try:
                    new_claims = await _verify_token(str(new_token), signer)
                except TokenInvalidError:
                    await websocket.close(code=_CLOSE_POLICY_VIOLATION)
                    return
                if new_claims.get("sub") != claims.get("sub") or new_claims.get(
                    "tenant_id"
                ) != claims.get("tenant_id"):
                    await websocket.close(code=_CLOSE_POLICY_VIOLATION)
                    return
                claims = new_claims
                continue

            if "subscribe" in data and isinstance(data["subscribe"], list):
                new_channels = []
                for intent in data["subscribe"]:
                    if not isinstance(intent, str):
                        continue
                    channel = await _resolve_subscription_intent(intent, claims, ownership)
                    if channel and channel not in active_channels:
                        new_channels.append(channel)

                if new_channels:
                    active_channels.extend(new_channels)
                    await manager.connect(websocket, new_channels)

    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
