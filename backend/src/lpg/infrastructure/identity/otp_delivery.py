"""`LoggingOtpDelivery` implements `application/identity/ports.py::OtpDeliveryPort`.

No SMS provider exists in this codebase yet (Phase 14, Notifications). Logs
the code at INFO instead of sending it. Constructed only when
`Settings.otp_delivery_dev_mode` is true — `model_post_init` already rejects
that flag outright outside local/dev, so this class existing at all implies
it's safe to log a code here.
"""

from __future__ import annotations

from lpg.config.logging import get_logger

_logger = get_logger(__name__)


class LoggingOtpDelivery:
    async def send(self, phone_number: str, code: str) -> None:
        _logger.info("otp_delivery_dev_mode", phone_number=phone_number, code=code)
