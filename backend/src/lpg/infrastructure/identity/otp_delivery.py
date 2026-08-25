"""`LoggingOtpDelivery` implements `application/identity/ports.py::OtpDeliveryPort`.

No SMS provider exists in this codebase yet (Phase 14, Notifications) — this
is the only implementation, used in every environment until one ships. Logs
the code at INFO instead of sending it.

Outside production it also stashes the plaintext code in Redis under a
short-TTL "dev inbox" key, readable back via the `/dev/otp-inbox/{phone_number}`
endpoint (`routers/dev_tools.py`, registered only when `not settings.
is_production` — same condition guards both). `OtpService` (the real OTP
store) only ever persists a salted hash, so without this there is no way —
short of scraping stdout — for a local/E2E test to learn a code the app
itself just generated and "sent". Guarded separately from the logging
above (which is a pre-existing gap, not this addition's to fix) so this
doesn't make a hypothetical production run any less safe than it already is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.config.settings import Settings
    from lpg.infrastructure.redis.client import RedisClient

_logger = get_logger(__name__)

_DEV_INBOX_TTL_SECONDS = 300


def dev_otp_inbox_key(phone_number: str) -> str:
    return f"dev:otp-inbox:{phone_number}"


class LoggingOtpDelivery:
    def __init__(self, redis: RedisClient, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def send(self, phone_number: str, code: str) -> None:
        _logger.info("otp_delivery_dev_mode", phone_number=phone_number, code=code)
        if not self._settings.is_production:
            await self._redis.client.set(
                dev_otp_inbox_key(phone_number), code, ex=_DEV_INBOX_TTL_SECONDS
            )
