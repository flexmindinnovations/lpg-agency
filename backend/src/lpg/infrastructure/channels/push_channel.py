"""Push notification channel — Firebase Cloud Messaging HTTP v1.

Two implementations:

* ``StubPushChannel`` — logs and returns, the default when no Firebase
  service-account credentials are configured. Mirrors the email/SMS stubs.
* ``FcmHttpV1PushChannel`` — real delivery. Mints an OAuth2 access token
  from the service-account key (cached for its lifetime) and POSTs to the
  FCM v1 ``send`` endpoint, one request per device token (v1 dropped the
  legacy multicast endpoint).

``build_push_channel(settings)`` picks between them.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import httpx
import jwt
import structlog

from lpg.application.notification.ports import PushTokenInvalidError

if TYPE_CHECKING:
    from lpg.config.settings import Settings

_logger = structlog.get_logger(__name__)

_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - public endpoint
_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_TOKEN_SKEW_SECONDS = 300


class StubPushChannel:
    """No Firebase configured — log the intent, deliver nothing."""

    async def send(
        self,
        *,
        token: str,
        platform: str,
        title: str,
        body: str,  # noqa: ARG002
        data: dict[str, str],
    ) -> None:
        _logger.info(
            "stub_push_send",
            token_suffix=token[-8:],
            platform=platform,
            title=title,
            data_keys=sorted(data),
        )


class FcmHttpV1PushChannel:
    """Real FCM v1 delivery. One instance per process; holds a cached
    access token and a shared ``httpx.AsyncClient``."""

    def __init__(
        self,
        *,
        service_account: dict[str, str],
        project_id: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._sa = service_account
        self._project_id = project_id
        self._endpoint = (
            f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        )
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._access_token: str | None = None
        self._access_token_expiry: float = 0.0

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._access_token_expiry - _TOKEN_SKEW_SECONDS:
            return self._access_token

        iat = int(now)
        assertion = jwt.encode(
            {
                "iss": self._sa["client_email"],
                "scope": _FCM_SCOPE,
                "aud": _OAUTH_TOKEN_URL,
                "iat": iat,
                "exp": iat + 3600,
            },
            self._sa["private_key"],
            algorithm="RS256",
        )
        response = await self._client.post(
            _OAUTH_TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = payload["access_token"]
        self._access_token_expiry = now + float(payload.get("expires_in", 3600))
        return self._access_token

    async def send(
        self,
        *,
        token: str,
        platform: str,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> None:
        access_token = await self._get_access_token()
        # `notification` gives the OS a tray entry when the app is
        # backgrounded; `data` is what the app reads on tap. Android also
        # gets the data in the foreground handler; iOS needs
        # `content-available` for that.
        message: dict[str, object] = {
            "token": token,
            "notification": {"title": title, "body": body},
            "data": data,
        }
        if platform == "ios":
            message["apns"] = {"payload": {"aps": {"content-available": 1}}}

        response = await self._client.post(
            self._endpoint,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": message},
        )
        if response.status_code in (404, 410):
            # UNREGISTERED / NOT_FOUND — the token is permanently dead.
            raise PushTokenInvalidError(token)
        response.raise_for_status()


def build_push_channel(settings: Settings) -> StubPushChannel | FcmHttpV1PushChannel:
    from pathlib import Path

    raw = ""
    path = settings.fcm_credentials_path.strip()
    if path:
        try:
            raw = Path(path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            _logger.error(
                "fcm_credentials_path_unreadable",
                path=path,
                error=str(exc),
                falling_back="StubPushChannel",
            )
            return StubPushChannel()
    else:
        raw = settings.fcm_credentials_json.get_secret_value().strip()

    if not raw:
        return StubPushChannel()

    try:
        service_account = json.loads(raw)
    except json.JSONDecodeError:
        _logger.error("fcm_credentials_not_json", falling_back="StubPushChannel")
        return StubPushChannel()

    project_id = settings.fcm_project_id or service_account.get("project_id", "")
    if not project_id or "client_email" not in service_account:
        _logger.error("fcm_credentials_incomplete", falling_back="StubPushChannel")
        return StubPushChannel()

    _logger.info("fcm_push_channel_enabled", project_id=project_id)
    return FcmHttpV1PushChannel(service_account=service_account, project_id=project_id)
