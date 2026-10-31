"""Pydantic models for `api/v1/routers/payment_gateway.py` (ADR-067)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class PaymentGatewaySettingsResponse(BaseModel):
    """Never carries a secret: a masked key id and "is it set" flags only."""

    configured: bool
    #: `agency` (own key), `platform` (shared default key), `demo` (no money
    #: moves) or `none` (online payment is off for this agency).
    source: Literal["agency", "platform", "demo", "none"]
    key_id_masked: str = ""
    #: From the key's own prefix: `rzp_test_…` is test, `rzp_live_…` is live.
    mode: Literal["test", "live"] | None = None
    has_key_secret: bool = False
    has_webhook_secret: bool = False
    #: Path to register in Razorpay (Settings > Webhooks), relative to the
    #: site origin. Empty until a key is saved.
    webhook_path: str = ""
    updated_at: datetime | None = None


class SetPaymentGatewayRequest(BaseModel):
    #: Leave blank to keep the saved key id.
    key_id: str = Field(default="", max_length=100)
    #: Leave blank to keep the saved secret (only when the key id is unchanged).
    key_secret: SecretStr = SecretStr("")
    #: Leave blank to keep the saved webhook secret.
    webhook_secret: SecretStr = SecretStr("")


class PaymentGatewayTestResponse(BaseModel):
    ok: bool
    message: str
