"""Unit tests for the push notification channel."""

from __future__ import annotations

import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from lpg.application.notification.ports import PushTokenInvalidError
from lpg.config.settings import Settings
from lpg.infrastructure.channels.push_channel import (
    FcmHttpV1PushChannel,
    StubPushChannel,
    build_push_channel,
)


def _service_account() -> dict[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return {
        "type": "service_account",
        "project_id": "lpg-test",
        "client_email": "fcm@lpg-test.iam.gserviceaccount.com",
        "private_key": pem,
    }


def _settings(**overrides: object) -> Settings:
    return Settings(environment="local", **overrides)  # type: ignore[arg-type]


# -- build_push_channel selection -------------------------------------------


def test_build_returns_stub_when_no_credentials() -> None:
    assert isinstance(build_push_channel(_settings()), StubPushChannel)


def test_build_returns_stub_when_credentials_not_json() -> None:
    channel = build_push_channel(_settings(fcm_credentials_json="not-json"))
    assert isinstance(channel, StubPushChannel)


def test_build_returns_stub_when_credentials_incomplete() -> None:
    channel = build_push_channel(
        _settings(fcm_credentials_json=json.dumps({"project_id": "x"}))
    )
    assert isinstance(channel, StubPushChannel)


def test_build_returns_fcm_channel_with_valid_credentials() -> None:
    channel = build_push_channel(
        _settings(fcm_credentials_json=json.dumps(_service_account()))
    )
    assert isinstance(channel, FcmHttpV1PushChannel)


# -- StubPushChannel -------------------------------------------------------


@pytest.mark.asyncio
async def test_stub_channel_send_is_a_noop() -> None:
    await StubPushChannel().send(
        token="t", platform="android", title="hi", body="there", data={}
    )


# -- FcmHttpV1PushChannel -------------------------------------------------------


def _mock_channel(handler) -> FcmHttpV1PushChannel:
    return FcmHttpV1PushChannel(
        service_account=_service_account(),
        project_id="lpg-test",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_fcm_send_mints_a_token_then_posts_the_message() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ya29.x", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer ya29.x"
        payload = json.loads(request.content)
        if payload["message"]["token"] == "device-1":
            assert payload["message"]["notification"]["title"] == "Order Confirmed"
            assert payload["message"]["data"]["type"] == "booking_confirmed"
        return httpx.Response(200, json={"name": "projects/lpg-test/messages/1"})

    channel = _mock_channel(handler)
    await channel.send(
        token="device-1",
        platform="android",
        title="Order Confirmed",
        body="Your order is in",
        data={"type": "booking_confirmed"},
    )
    assert [r.url.host for r in seen] == ["oauth2.googleapis.com", "fcm.googleapis.com"]

    # Second send reuses the cached access token — no new OAuth round trip.
    seen.clear()
    await channel.send(
        token="device-2", platform="ios", title="t", body="b", data={}
    )
    assert [r.url.host for r in seen] == ["fcm.googleapis.com"]


@pytest.mark.asyncio
async def test_fcm_send_raises_push_token_invalid_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ya29.x", "expires_in": 3600})
        return httpx.Response(404, json={"error": {"status": "NOT_FOUND"}})

    channel = _mock_channel(handler)
    with pytest.raises(PushTokenInvalidError):
        await channel.send(
            token="dead-token", platform="android", title="t", body="b", data={}
        )


@pytest.mark.asyncio
async def test_fcm_send_raises_on_other_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ya29.x", "expires_in": 3600})
        return httpx.Response(500, json={"error": {"status": "INTERNAL"}})

    channel = _mock_channel(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await channel.send(
            token="t", platform="android", title="t", body="b", data={}
        )
