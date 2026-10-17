"""Meta WhatsApp Cloud API webhook (ADR-055).

`GET /webhooks/whatsapp` answers Meta's one-time subscription handshake;
`POST /webhooks/whatsapp` receives customer messages.

Neither endpoint takes a JWT: Meta is the caller. The POST is authenticated by
the `X-Hub-Signature-256` HMAC over the raw body (Meta app secret), checked
before the body is parsed. The tenant is not known here; the background job
resolves it from the receiving business number.

The POST only records intent and returns 200 quickly: each message is
enqueued as its own `handle_whatsapp_message` job, keyed by Meta's message
id, so Meta's retries of the same delivery collapse into one job.

Both routes are left out of the OpenAPI document: they are Meta's contract,
not one the dashboard or mobile clients generate code from (ADR-026).
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from lpg.api.v1.dependencies.order import get_job_queue
from lpg.application.common.ports import JobQueuePort
from lpg.config.logging import get_logger
from lpg.config.settings import get_settings
from lpg.infrastructure.whatsapp.webhook import (
    HANDLE_MESSAGE_JOB,
    job_id_for,
    parse_inbound_messages,
    verify_signature,
)

router = APIRouter(tags=["WhatsApp"], include_in_schema=False)

_logger = get_logger(__name__)


@router.get("/webhooks/whatsapp")
async def verify_whatsapp_webhook(
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> Response:
    """Echo `hub.challenge` when the verify token matches, as Meta requires."""
    import hmac

    secret = get_settings().whatsapp_verify_token
    expected = secret.get_secret_value() if secret is not None else ""
    if (
        mode != "subscribe"
        or not expected
        or not verify_token
        or not hmac.compare_digest(verify_token, expected)
        or challenge is None
    ):
        raise HTTPException(status_code=403, detail="Webhook verification failed.")
    return Response(content=challenge, media_type="text/plain")


@router.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(
    request: Request,
    job_queue: Annotated[JobQueuePort, Depends(get_job_queue)],
) -> dict[str, int]:
    app_secret = get_settings().whatsapp_app_secret
    raw_body = await request.body()
    if app_secret is None or not verify_signature(
        app_secret=app_secret.get_secret_value(),
        raw_body=raw_body,
        signature_header=request.headers.get("X-Hub-Signature-256"),
    ):
        _logger.warning("whatsapp_webhook_signature_rejected")
        raise HTTPException(status_code=403, detail="Invalid signature.")

    try:
        payload = json.loads(raw_body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Body is not valid JSON.") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")

    messages = parse_inbound_messages(payload)
    for message in messages:
        await job_queue.enqueue(
            HANDLE_MESSAGE_JOB,
            {
                "phone_number_id": message.phone_number_id,
                "wa_message_id": message.wa_message_id,
                "from_phone": message.from_phone,
                "profile_name": message.profile_name,
                "text": message.text,
            },
            _job_id=job_id_for(message.wa_message_id),
        )
    return {"received": len(messages)}
