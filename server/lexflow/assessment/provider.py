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

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from lexflow.analysis.provider import ASK_AN_ADMINISTRATOR, Response, Unavailable
from lexflow.assessment.inputs import Inputs
from lexflow.config import Settings

PROVIDER_LABELS = {"scripted": "Scripted test provider (not AI)"}


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
    from lexflow.assessment.scripted import ScriptedAssessmentProvider

    return ScriptedAssessmentProvider()
