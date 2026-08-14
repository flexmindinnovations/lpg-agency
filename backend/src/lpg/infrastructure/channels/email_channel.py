"""Email channel stub."""

import structlog

_logger = structlog.get_logger(__name__)


class StubEmailChannel:
    """Phase 15 stub — logs the email, doesn't call an external provider."""

    async def send(self, *, to: str, subject: str, body: str) -> None:
        _logger.info("stub_email_send", to=to, subject=subject)
