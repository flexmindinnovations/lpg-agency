"""`LoggingEmailSender` implements `application/identity/ports.py::EmailSender`.

Same story as `LoggingOtpDelivery` — no real email provider exists yet
(Phase 14). Logs the message instead of sending it.
"""

from __future__ import annotations

from lpg.config.logging import get_logger

_logger = get_logger(__name__)


class LoggingEmailSender:
    async def send(self, to: str, subject: str, body: str) -> None:
        _logger.info("email_delivery_dev_mode", to=to, subject=subject, body=body)
