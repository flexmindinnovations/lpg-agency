"""Unit tests for the SMS channel and the SMS-backed OTP delivery."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from lpg.application.common.errors import ServiceUnavailableError
from lpg.application.notification.ports import SmsDeliveryError, SmsTemplate
from lpg.config.settings import Settings
from lpg.infrastructure.channels.sms_channel import (
    Msg91SmsChannel,
    StubSmsChannel,
    build_sms_channel,
    template_ids,
)
from lpg.infrastructure.identity.otp_delivery import SmsOtpDelivery, dev_otp_inbox_key

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


def _settings(**overrides: object) -> Settings:
    return Settings(environment="local", **overrides)  # type: ignore[arg-type]


# -- build_sms_channel selection --------------------------------------------


def test_build_returns_stub_by_default() -> None:
    assert isinstance(build_sms_channel(_settings()), StubSmsChannel)


def test_build_returns_stub_when_msg91_has_no_auth_key() -> None:
    assert isinstance(build_sms_channel(_settings(sms_provider="msg91")), StubSmsChannel)


def test_build_returns_msg91_channel_with_an_auth_key() -> None:
    channel = build_sms_channel(_settings(sms_provider="msg91", msg91_auth_key="k"))
    assert isinstance(channel, Msg91SmsChannel)


def test_template_ids_skip_unset_and_blank_ids() -> None:
    ids = template_ids(
        _settings(sms_template_login_otp=" tpl-login ", sms_template_delivery_otp="  ")
    )
    assert ids == {SmsTemplate.LOGIN_OTP: "tpl-login"}


@pytest.mark.asyncio
async def test_stub_channel_send_is_a_noop() -> None:
    await StubSmsChannel().send(
        to="+919876543210", body="hi", template=SmsTemplate.LOGIN_OTP, variables={}
    )


# -- Msg91SmsChannel ----------------------------------------------------------


def _msg91(
    handler: Callable[[httpx.Request], httpx.Response],
    ids: Mapping[SmsTemplate, str] | None = None,
) -> Msg91SmsChannel:
    return Msg91SmsChannel(
        auth_key="test-auth-key",
        template_ids=ids if ids is not None else {SmsTemplate.OUT_FOR_DELIVERY: "tpl-ofd"},
        base_url="https://msg91.test/",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


async def _send(channel: Msg91SmsChannel, to: str = "+919876543210") -> None:
    await channel.send(
        to=to,
        body="Your order #AB12CD34 is out for delivery.",
        template=SmsTemplate.OUT_FOR_DELIVERY,
        variables={"order_ref": "AB12CD34"},
    )


@pytest.mark.asyncio
async def test_msg91_posts_the_flow_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"type": "success", "message": "req-1"})

    await _send(_msg91(handler))

    assert len(seen) == 1
    request = seen[0]
    assert str(request.url) == "https://msg91.test/api/v5/flow"
    assert request.headers["authkey"] == "test-auth-key"
    assert json.loads(request.content) == {
        "template_id": "tpl-ofd",
        "short_url": "0",
        "recipients": [{"mobiles": "919876543210", "order_ref": "AB12CD34"}],
    }


@pytest.mark.asyncio
async def test_msg91_raises_when_the_template_is_not_configured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("no request should be made without a template ID")

    with pytest.raises(SmsDeliveryError, match="out_for_delivery"):
        await _send(_msg91(handler, ids={}))


@pytest.mark.asyncio
async def test_msg91_rejects_a_number_that_is_not_e164() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("no request should be made for an invalid number")

    with pytest.raises(SmsDeliveryError, match=r"E\.164"):
        await _send(_msg91(handler), to="98765-43210")


@pytest.mark.asyncio
async def test_msg91_raises_on_an_error_body_with_http_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"type": "error", "message": "Invalid template"})

    with pytest.raises(SmsDeliveryError, match="Invalid template"):
        await _send(_msg91(handler))


@pytest.mark.asyncio
async def test_msg91_raises_on_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorised")

    with pytest.raises(SmsDeliveryError, match="HTTP 401"):
        await _send(_msg91(handler))


@pytest.mark.asyncio
async def test_msg91_raises_when_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(SmsDeliveryError, match="unreachable"):
        await _send(_msg91(handler))


# -- SmsOtpDelivery -----------------------------------------------------------


class _RecordingSmsChannel:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self._error = error

    async def send(
        self,
        *,
        to: str,
        body: str,
        template: SmsTemplate,
        variables: Mapping[str, str],
    ) -> None:
        self.calls.append({"to": to, "body": body, "template": template, "variables": variables})
        if self._error is not None:
            raise self._error


class _FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.client = self

    async def set(self, key: str, value: str, ex: int) -> None:  # noqa: ARG002
        self.values[key] = value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("purpose", "template"),
    [("login", SmsTemplate.LOGIN_OTP), ("delivery", SmsTemplate.DELIVERY_OTP)],
)
async def test_sms_otp_delivery_sends_the_purpose_template(
    purpose: str, template: SmsTemplate
) -> None:
    channel = _RecordingSmsChannel()
    redis = _FakeRedisClient()
    delivery = SmsOtpDelivery(channel, redis, _settings())  # type: ignore[arg-type]

    await delivery.send("+919876543210", "482913", purpose=purpose)  # type: ignore[arg-type]

    assert len(channel.calls) == 1
    assert channel.calls[0]["template"] is template
    assert channel.calls[0]["variables"] == {"otp": "482913"}
    # Delivery codes get their own inbox slot, so a login OTP can't overwrite one.
    assert redis.values[dev_otp_inbox_key("+919876543210", purpose)] == "482913"  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_sms_otp_delivery_skips_the_dev_inbox_in_production() -> None:
    redis = _FakeRedisClient()
    settings = Settings(environment="production", cors_origins=["https://lpg.test"])
    delivery = SmsOtpDelivery(_RecordingSmsChannel(), redis, settings)  # type: ignore[arg-type]

    await delivery.send("+919876543210", "482913")

    assert redis.values == {}


@pytest.mark.asyncio
async def test_sms_otp_delivery_turns_a_provider_failure_into_503() -> None:
    channel = _RecordingSmsChannel(error=SmsDeliveryError("MSG91 down"))
    delivery = SmsOtpDelivery(channel, _FakeRedisClient(), _settings())  # type: ignore[arg-type]

    with pytest.raises(ServiceUnavailableError):
        await delivery.send("+919876543210", "482913")
