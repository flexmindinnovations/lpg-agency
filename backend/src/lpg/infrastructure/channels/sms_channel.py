"""SMS channel stub."""

import structlog

_logger = structlog.get_logger(__name__)


class StubSmsChannel:
    """Phase 15 stub — logs the SMS, doesn't call an external provider."""

    async def send(self, *, to: str, body: str) -> None:  # noqa: ARG002
        _logger.info("stub_sms_send", to=to)
