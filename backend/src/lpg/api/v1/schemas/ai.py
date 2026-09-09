"""Pydantic request/response models for `api/v1/routers/ai.py` (ADR-045)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AskAiAssistantRequest(BaseModel):
    question: str = Field(min_length=3)


class AskAiAssistantResponse(BaseModel):
    answer: str | None
    tools_used: list[str]
    #: `None` means the model answered normally. Otherwise the frontend
    #: renders a specific, non-error message — none of these are exceptional
    #: conditions from the caller's point of view.
    disabled_reason: Literal["gateway_disabled", "budget_exceeded", "provider_error"] | None
