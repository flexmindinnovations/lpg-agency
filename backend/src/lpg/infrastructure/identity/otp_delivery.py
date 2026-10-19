"""`OtpDeliveryPort` implementations (`application/identity/ports.py`).

`SmsOtpDelivery` sends the code as an SMS through the configured
`SmsChannel` (MSG91 today), used whenever `LPG_SMS_PROVIDER` names a real
provider. `LoggingOtpDelivery` is the no-provider fallback: it logs the code
at INFO instead of sending it.

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

from lpg.application.common.errors import ServiceUnavailableError
from lpg.application.notification.ports import SmsDeliveryError, SmsTemplate
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.application.identity.ports import OtpPurpose
    from lpg.application.notification.ports import SmsChannel
    from lpg.config.settings import Settings
    from lpg.infrastructure.redis.client import RedisClient

_logger = get_logger(__name__)

_DEV_INBOX_TTL_SECONDS = 300


def dev_otp_inbox_key(phone_number: str, purpose: OtpPurpose = "login") -> str:
    # Delivery codes get their own slot so a customer signing in mid-delivery
    # doesn't overwrite the code the driver's testing banner reads back.
    if purpose == "delivery":
        return f"dev:otp-inbox:delivery:{phone_number}"
    return f"dev:otp-inbox:{phone_number}"


async def _stash_in_dev_inbox(
    redis: RedisClient, settings: Settings, phone_number: str, code: str, purpose: OtpPurpose
) -> None:
    if not settings.is_production:
        ttl = settings.delivery_otp_ttl_seconds if purpose == "delivery" else _DEV_INBOX_TTL_SECONDS
        await redis.client.set(dev_otp_inbox_key(phone_number, purpose), code, ex=ttl)


class LoggingOtpDelivery:
    def __init__(self, redis: RedisClient, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    async def send(
        self,
        phone_number: str,
        code: str,
        *,
        purpose: OtpPurpose = "login",
    ) -> None:
        _logger.info("otp_delivery_dev_mode", phone_number=phone_number, code=code, purpose=purpose)
        await _stash_in_dev_inbox(self._redis, self._settings, phone_number, code, purpose)


_OTP_TEMPLATES: dict[OtpPurpose, SmsTemplate] = {
    "login": SmsTemplate.LOGIN_OTP,
    "delivery": SmsTemplate.DELIVERY_OTP,
}


def _otp_body(purpose: OtpPurpose, code: str) -> str:
    if purpose == "delivery":
        return f"{code} is the OTP to confirm your LPG cylinder delivery."
    return f"{code} is your OTP to sign in."


class SmsOtpDelivery:
    """Sends the code by SMS. Never logs the code itself.

    Outside production the code also lands in the dev inbox, exactly as with
    `LoggingOtpDelivery`, so UAT/E2E runs keep working against a real
    provider without needing the handset.
    """

    def __init__(self, sms_channel: SmsChannel, redis: RedisClient, settings: Settings) -> None:
        self._sms_channel = sms_channel
        self._redis = redis
        self._settings = settings

    async def send(
        self,
        phone_number: str,
        code: str,
        *,
        purpose: OtpPurpose = "login",
    ) -> None:
        await _stash_in_dev_inbox(self._redis, self._settings, phone_number, code, purpose)
        try:
            await self._sms_channel.send(
                to=phone_number,
                body=_otp_body(purpose, code),
                template=_OTP_TEMPLATES[purpose],
                variables={"otp": code},
            )
        except SmsDeliveryError as exc:
            _logger.error("otp_sms_failed", purpose=purpose, error=str(exc))
            msg = "We couldn't send the OTP right now. Please try again in a minute."
            raise ServiceUnavailableError(msg) from exc
