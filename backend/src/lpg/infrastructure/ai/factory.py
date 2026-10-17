"""Picks the `ModelGatewayPort` adapter from `Settings.ai_provider`.

This one function is the entire "provider configurable" story (ADR-045): a
second provider means one new adapter class implementing `ModelGatewayPort`
plus one new branch here — nothing above this layer changes, the same way
`FileStorage`/`DocumentOcrPort` already prove storage/OCR are swappable.

An unrecognized `ai_provider` value raises at first use, not a silent
fallback to Gemini — fail-loud-on-misconfiguration, matching this codebase's
convention (e.g. `Settings`' own env-var-source validation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lpg.application.ai.ports import ModelGatewayPort
    from lpg.config.settings import Settings


def get_model_gateway(settings: Settings) -> ModelGatewayPort:
    if settings.ai_provider == "gemini":
        from lpg.infrastructure.ai.gemini_adapter import GeminiModelGateway

        return GeminiModelGateway(
            api_key=settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else "",
            model=settings.gemini_model,
        )
    if settings.ai_provider == "anthropic":
        from lpg.infrastructure.ai.anthropic_adapter import AnthropicModelGateway

        return AnthropicModelGateway(
            api_key=(
                settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
            ),
            model=settings.anthropic_model,
            effort=settings.anthropic_effort,
        )
    msg = (
        f"Unknown ai_provider '{settings.ai_provider}'. "
        "Only 'gemini' and 'anthropic' are implemented — add a new adapter "
        "class and a branch here before configuring a different value."
    )
    raise ValueError(msg)
