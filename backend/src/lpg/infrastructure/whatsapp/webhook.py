"""Meta WhatsApp webhook helpers: signature check and payload parsing.

Pure functions with no framework or database dependency, so the API router
can call them directly and they are trivially unit-testable.

Meta signs every webhook POST with `X-Hub-Signature-256: sha256=<hex>`, an
HMAC-SHA256 of the raw request body keyed by the Meta app secret. That
signature is the only thing that proves a request came from Meta, so it is
checked against the exact bytes received, before any parsing.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from lpg.application.whatsapp.ports import InboundWhatsAppMessage

_SIGNATURE_PREFIX = "sha256="

#: The ARQ job that answers one message (`infrastructure/jobs/whatsapp_jobs.py`).
#: Named here so the webhook can enqueue it without importing the job module
#: and, through it, the persistence layer.
HANDLE_MESSAGE_JOB = "handle_whatsapp_message"

#: Longer messages are cut before they reach the model or the log.
MAX_TEXT_LENGTH = 2000


def verify_signature(*, app_secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    if not app_secret or not signature_header:
        return False
    if not signature_header.startswith(_SIGNATURE_PREFIX):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header[len(_SIGNATURE_PREFIX) :])


def parse_inbound_messages(payload: dict[str, Any]) -> list[InboundWhatsAppMessage]:
    """Customer messages in a `whatsapp_business_account` webhook payload.

    Status callbacks (sent/delivered/read receipts) carry no `messages` and
    yield nothing. Non-text messages become a short bracketed description,
    so the assistant can tell the customer it only reads text instead of
    staying silent.
    """
    if payload.get("object") != "whatsapp_business_account":
        return []
    messages: list[InboundWhatsAppMessage] = []
    for entry in _dicts(payload.get("entry")):
        for change in _dicts(entry.get("changes")):
            value = change.get("value")
            if change.get("field") != "messages" or not isinstance(value, dict):
                continue
            metadata = value.get("metadata")
            phone_number_id = (
                metadata.get("phone_number_id") if isinstance(metadata, dict) else None
            )
            if not isinstance(phone_number_id, str):
                continue
            names = {
                contact.get("wa_id"): (contact.get("profile") or {}).get("name")
                for contact in _dicts(value.get("contacts"))
            }
            for message in _dicts(value.get("messages")):
                parsed = _parse_message(phone_number_id, message, names)
                if parsed is not None:
                    messages.append(parsed)
    return messages


def _parse_message(
    phone_number_id: str, message: dict[str, Any], names: dict[Any, Any]
) -> InboundWhatsAppMessage | None:
    wa_message_id = message.get("id")
    sender = message.get("from")
    if not isinstance(wa_message_id, str) or not isinstance(sender, str) or not sender.isdigit():
        return None
    text = _message_text(message)
    if not text:
        return None
    name = names.get(sender)
    return InboundWhatsAppMessage(
        phone_number_id=phone_number_id,
        wa_message_id=wa_message_id,
        from_phone=f"+{sender}",
        profile_name=name if isinstance(name, str) else None,
        text=text[:MAX_TEXT_LENGTH],
    )


def _message_text(message: dict[str, Any]) -> str | None:
    kind = message.get("type")
    if kind == "text":
        body = (message.get("text") or {}).get("body")
        return body.strip() if isinstance(body, str) else None
    if kind == "button":
        body = (message.get("button") or {}).get("text")
        return body.strip() if isinstance(body, str) else None
    if kind == "interactive":
        interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        title = reply.get("title")
        return title.strip() if isinstance(title, str) else None
    if kind in ("image", "audio", "video", "document", "sticker", "location", "contacts"):
        return f"[The customer sent a {kind} message, which the assistant cannot read.]"
    return None


def _dicts(value: object) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def job_id_for(wa_message_id: str) -> str:
    """The ARQ job id for a message: Meta's own id, so re-deliveries of the
    same message collapse into one queued job."""
    return f"whatsapp:{wa_message_id}"
