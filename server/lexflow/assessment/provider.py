"""The provider seam for outcome assessments (D7-2).

Shaped like Phase 5's (``lexflow.analysis.provider``): a provider has a name,
a model and ``generate(request)``, and failures are ``ProviderError`` with a
safe code and message. Only the **scripted** assessment provider can be
built. There is no code path that sends an assessment to a real model: with
``LEXFLOW_AI_PROVIDER=gemini`` assessments are reported unavailable, because a
real model needs the owner's approval (register R7). Unknown providers fail
closed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol, cast, runtime_checkable

from lexflow.analysis.provider import ASK_AN_ADMINISTRATOR, Response, Unavailable
from lexflow.assessment.inputs import Inputs
from lexflow.config import Settings, is_test_database

PROVIDER_LABELS = {
    "scripted": "Scripted test provider (not AI)",
    "gemini": "Google Gemini API (AI)",
}


@dataclass(frozen=True)
class AssessmentRequest:
    system_instruction: str
    prompt: str
    response_schema: dict[str, Any]
    max_output_tokens: int
    # The inputs behind the prompt; the scripted double builds its answer from them.
    inputs: Inputs


@runtime_checkable
class AssessmentProvider(Protocol):
    name: str
    model: str

    def generate(self, request: AssessmentRequest) -> Response: ...


def unavailable_reason(settings: Settings) -> Unavailable | None:
    if not settings.outcome_assessment:
        return Unavailable(
            "assessment-disabled",
            "Outcome assessment is switched off on this server.",
            detail="LEXFLOW_OUTCOME_ASSESSMENT is false (the default).",
        )
    if settings.ai_provider == "scripted":
        return None
    if settings.ai_provider == "gemini" and settings.ai_approved_case_ids:
        return None  # the owner approved a real model for listed cases (allowed_for)
    if settings.ai_provider == "gemini":
        return Unavailable(
            "assessment-model-not-approved",
            "Outcome assessment with a real AI model is not enabled on this server: it needs "
            "the owner's approval. " + ASK_AN_ADMINISTRATOR,
            detail=(
                "Phase 7 is a synthetic-only demo: only LEXFLOW_AI_PROVIDER=scripted can produce "
                "assessments (register R7)."
            ),
        )
    return Unavailable(
        "analysis-disabled",
        "AI analysis is turned off on this server.",
        detail="LEXFLOW_AI_PROVIDER=disabled in server/.env.",
    )


def provider_for(settings: Settings) -> AssessmentProvider | Unavailable:
    missing = unavailable_reason(settings)
    if missing is not None:
        return missing
    if settings.ai_provider == "gemini":
        return GeminiAssessmentProvider(settings)
    from lexflow.assessment.scripted import ScriptedAssessmentProvider

    return ScriptedAssessmentProvider()


def allowed_for(settings: Settings, case_id: uuid.UUID) -> bool:
    """May this case be assessed here? Always on a test or e2e database (the
    synthetic demo); elsewhere only a case the owner listed in
    LEXFLOW_AI_APPROVED_CASE_IDS."""
    return is_test_database(settings.database_url) or case_id in settings.ai_approved_case_ids


class GeminiAssessmentProvider:
    """The analysis' Gemini client, asked with the assessment prompt and schema.

    It is AI: its answer goes through the same assessment validation as any
    provider's (accepted findings and precedents only, no probabilities, no
    invented citations) before anything is stored or shown."""

    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        from lexflow.analysis.provider import GeminiProvider

        if settings.gemini_api_key is None or settings.gemini_model is None:
            raise ValueError("Gemini is not configured (unavailable_reason reports it).")
        self.model = settings.gemini_model
        self._inner = GeminiProvider(
            settings.gemini_api_key, self.model, timeout_seconds=settings.ai_timeout_seconds
        )

    def generate(self, request: AssessmentRequest) -> Response:
        # GeminiProvider reads only the instruction, prompt, schema and token limit,
        # which an assessment request carries under the same names.
        return self._inner.generate(cast(Any, request))
