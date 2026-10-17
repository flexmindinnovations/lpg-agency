"""SMS channel — implements `application/notification/ports.py::SmsChannel`.

Two implementations:

* ``StubSmsChannel`` — logs and returns, the default when no provider is
  configured (``LPG_SMS_PROVIDER=stub``). Mirrors the email/push stubs.
* ``Msg91SmsChannel`` — real delivery through MSG91's Flow API, which sends a
  pre-approved (DLT-bound) template with its variables filled in.

``build_sms_channel(settings)`` picks between them. A second provider (Twilio,
Gupshup) is one more class with the same ``send`` signature plus a branch
here; nothing above the port changes.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import httpx
import structlog

from lpg.application.notification.ports import SmsDeliveryError, SmsTemplate

if TYPE_CHECKING:
    from collections.abc import Mapping

    from lpg.config.settings import Settings

_logger = structlog.get_logger(__name__)

_E164 = re.compile(r"^\+?[1-9]\d{9,14}$")


def mask_phone(phone_number: str) -> str:
    """Last four digits only — enough to correlate a log line with a
    complaint, not enough to be a phone-number leak."""
    return f"***{phone_number[-4:]}"


def template_ids(settings: Settings) -> dict[SmsTemplate, str]:
    """Provider template ID per message, from configuration. Unset IDs are
    left out, so a lookup miss means "not configured"."""
    configured = {
        SmsTemplate.LOGIN_OTP: settings.sms_template_login_otp,
        SmsTemplate.DELIVERY_OTP: settings.sms_template_delivery_otp,
        SmsTemplate.BOOKING_CONFIRMED: settings.sms_template_booking_confirmed,
        SmsTemplate.OUT_FOR_DELIVERY: settings.sms_template_out_for_delivery,
        SmsTemplate.DELIVERY_CONFIRMED: settings.sms_template_delivery_confirmed,
    }
    return {template: tid.strip() for template, tid in configured.items() if tid.strip()}


class StubSmsChannel:
    """No provider configured — log the intent, deliver nothing."""

    async def send(
        self,
        *,
        to: str,
        body: str,  # noqa: ARG002
        template: SmsTemplate,
        variables: Mapping[str, str],  # noqa: ARG002
    ) -> None:
        _logger.info("stub_sms_send", to=mask_phone(to), template=template.value)


class Msg91SmsChannel:
    """MSG91 Flow API (``POST /api/v5/flow``). One instance per process; holds
    a shared ``httpx.AsyncClient``.

    The sender ID, DLT entity ID and DLT template ID are attached to the
    MSG91 template itself, so a request names only the MSG91 template ID and
    the variable values. Variable keys must match the ``##name##``
    placeholders in the MSG91 template.
    """

    def __init__(
        self,
        *,
        auth_key: str,
        template_ids: Mapping[SmsTemplate, str],
        base_url: str = "https://control.msg91.com",
        timeout_seconds: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._auth_key = auth_key
        self._template_ids = dict(template_ids)
        self._endpoint = f"{base_url.rstrip('/')}/api/v5/flow"
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def send(
        self,
        *,
        to: str,
        body: str,  # noqa: ARG002 - MSG91 renders the registered template, not free text
        template: SmsTemplate,
        variables: Mapping[str, str],
    ) -> None:
        template_id = self._template_ids.get(template)
        if template_id is None:
            msg = f"No MSG91 template ID configured for SMS template {template.value!r}."
            raise SmsDeliveryError(msg)
        if not _E164.match(to):
            msg = f"Phone number {mask_phone(to)} is not in E.164 format."
            raise SmsDeliveryError(msg)

        recipient = {"mobiles": to.removeprefix("+"), **variables}
        try:
            response = await self._client.post(
                self._endpoint,
                headers={"authkey": self._auth_key, "accept": "application/json"},
                json={"template_id": template_id, "short_url": "0", "recipients": [recipient]},
            )
        except httpx.HTTPError as exc:
            msg = f"MSG91 unreachable: {type(exc).__name__}"
            raise SmsDeliveryError(msg) from exc

        # MSG91 can answer 200 with `{"type": "error"}`, so the body decides,
        # not only the status code.
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if response.is_error or payload.get("type") != "success":
            msg = f"MSG91 rejected the SMS (HTTP {response.status_code}): {payload.get('message')}"
            raise SmsDeliveryError(msg)

        _logger.info(
            "sms_sent",
            provider="msg91",
            to=mask_phone(to),
            template=template.value,
            request_id=payload.get("message"),
        )


def build_sms_channel(settings: Settings) -> StubSmsChannel | Msg91SmsChannel:
    if settings.sms_provider == "msg91":
        auth_key = settings.msg91_auth_key.get_secret_value().strip()
        if not auth_key:
            _logger.error("msg91_auth_key_missing", falling_back="StubSmsChannel")
            return StubSmsChannel()
        ids = template_ids(settings)
        missing = sorted(t.value for t in SmsTemplate if t not in ids)
        if missing:
            # Not fatal: the configured messages still go out; each missing
            # one fails at send time and is recorded in the notification log.
            _logger.warning("sms_templates_missing", provider="msg91", templates=missing)
        _logger.info("msg91_sms_channel_enabled")
        return Msg91SmsChannel(
            auth_key=auth_key,
            template_ids=ids,
            base_url=settings.msg91_base_url,
            timeout_seconds=settings.sms_request_timeout_seconds,
        )
    return StubSmsChannel()
