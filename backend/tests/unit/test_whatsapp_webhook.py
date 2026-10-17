"""Unit tests for the WhatsApp webhook helpers (ADR-052): Meta's signature
check and payload parsing."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from lpg.infrastructure.whatsapp.webhook import (
    MAX_TEXT_LENGTH,
    parse_inbound_messages,
    verify_signature,
)

_SECRET = "app-secret"


def _sign(body: bytes, secret: str = _SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted() -> None:
    body = b'{"object":"whatsapp_business_account"}'
    assert verify_signature(app_secret=_SECRET, raw_body=body, signature_header=_sign(body))


def test_signature_over_other_bytes_is_rejected() -> None:
    body = b'{"a":1}'
    assert not verify_signature(
        app_secret=_SECRET, raw_body=body + b" ", signature_header=_sign(body)
    )


def test_signature_with_wrong_secret_is_rejected() -> None:
    body = b"{}"
    assert not verify_signature(
        app_secret=_SECRET, raw_body=body, signature_header=_sign(body, "other")
    )


def test_missing_or_malformed_signature_is_rejected() -> None:
    assert not verify_signature(app_secret=_SECRET, raw_body=b"{}", signature_header=None)
    assert not verify_signature(app_secret=_SECRET, raw_body=b"{}", signature_header="md5=abc")
    assert not verify_signature(app_secret="", raw_body=b"{}", signature_header=_sign(b"{}", ""))


def _payload(*messages: dict[str, Any], phone_number_id: str = "1111") -> dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550001111",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [{"wa_id": "919876543210", "profile": {"name": "Asha"}}],
                            "messages": list(messages),
                        },
                    }
                ],
            }
        ],
    }


def _message(kind: str = "text", **fields: Any) -> dict[str, Any]:
    return {"from": "919876543210", "id": f"wamid.{kind}", "type": kind, **fields}


def test_text_message_is_parsed() -> None:
    [message] = parse_inbound_messages(_payload(_message(text={"body": "  Book a cylinder "})))

    assert message.phone_number_id == "1111"
    assert message.wa_message_id == "wamid.text"
    assert message.from_phone == "+919876543210"
    assert message.profile_name == "Asha"
    assert message.text == "Book a cylinder"


def test_button_and_list_replies_use_their_title() -> None:
    messages = parse_inbound_messages(
        _payload(
            _message("interactive", interactive={"button_reply": {"id": "y", "title": "Yes"}}),
            _message("button", button={"text": "Track order"}),
        )
    )
    assert [m.text for m in messages] == ["Yes", "Track order"]


def test_media_message_becomes_a_description() -> None:
    [message] = parse_inbound_messages(_payload(_message("image", image={"id": "m"})))
    assert "image" in message.text


def test_long_text_is_truncated() -> None:
    [message] = parse_inbound_messages(_payload(_message(text={"body": "x" * 5000})))
    assert len(message.text) == MAX_TEXT_LENGTH


def test_status_callbacks_and_other_objects_yield_nothing() -> None:
    status_only = _payload()
    status_only["entry"][0]["changes"][0]["value"].pop("messages")
    status_only["entry"][0]["changes"][0]["value"]["statuses"] = [{"id": "wamid.x"}]

    assert parse_inbound_messages(status_only) == []
    assert parse_inbound_messages({"object": "page", "entry": []}) == []
    assert parse_inbound_messages(_payload(_message("reaction", reaction={}))) == []


def test_malformed_sender_is_skipped() -> None:
    bad = _message(text={"body": "hi"})
    bad["from"] = "not-a-number"
    assert parse_inbound_messages(_payload(bad)) == []
