"""Unit tests for `get_model_gateway` (ADR-045) — provider selection is the
entire "provider configurable" story, so it gets its own focused coverage."""

from __future__ import annotations

import pytest

from lpg.config.settings import Settings
from lpg.infrastructure.ai.factory import get_model_gateway
from lpg.infrastructure.ai.gemini_adapter import GeminiModelGateway


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "ai_provider": "gemini",
        "gemini_api_key": None,
        "gemini_model": "gemini-2.0-flash",
    }
    defaults.update(overrides)
    # `model_construct` bypasses validation (deliberately — a full `Settings`
    # needs a real DB/Redis URL etc. this test has no use for), which is
    # also why its generated stub expects every field's exact type rather
    # than a loosely-typed kwargs dict; test-only scaffolding, not a real
    # type hazard.
    return Settings.model_construct(**defaults)  # type: ignore[arg-type]


def test_gemini_provider_returns_a_gemini_gateway() -> None:
    gateway = get_model_gateway(_settings())
    assert isinstance(gateway, GeminiModelGateway)


def test_unknown_provider_raises_rather_than_silently_falling_back() -> None:
    with pytest.raises(ValueError, match="Unknown ai_provider"):
        get_model_gateway(_settings(ai_provider="openai"))
