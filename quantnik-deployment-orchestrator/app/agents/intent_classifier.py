from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.requests import ChildAgentType, INTENT_TO_AGENT, IntentType


class ClassifiedIntent(BaseModel):
    intent: IntentType = Field(...)
    target_agent: ChildAgentType = Field(...)
    confidence: float = Field(..., ge=0, le=1)
    entities: dict[str, Any] = Field(default_factory=dict)
    requires_clarification: bool = False
    clarification_question: str | None = None
    reasoning: str | None = None


class IntentClassifier:
    async def classify(self, message: str, context: dict[str, Any] | None = None) -> ClassifiedIntent:
        context = context or {}
        normalized = message.lower().strip()

        if context.get("ci_pipeline_request"):
            ci_request = context.get("ci_pipeline_request") or {}
            target = ci_request.get("target", {}) if isinstance(ci_request, dict) else {}
            return ClassifiedIntent(
                intent=IntentType.GENERATE_CI_PIPELINE,
                target_agent=ChildAgentType.CI,
                confidence=0.99,
                entities={
                    "pipeline_type": "ci",
                    "platform": target.get("platform"),
                },
                reasoning="Structured CI pipeline payload was provided in context.",
            )

        if normalized in {"yes", "ok", "okay", "proceed", "continue", "1", "one"}:
            return ClassifiedIntent(
                intent=IntentType.CONFIRMATION,
                target_agent=ChildAgentType.UNKNOWN,
                confidence=0.95,
                reasoning="Confirmation response detected.",
            )

        if any(token in normalized for token in [
            "ci", "build pipeline", "continuous integration", "generate pipeline",
            "github actions", "gitlab ci", "azure pipeline", "azure devops", "harness"
        ]):
            return ClassifiedIntent(
                intent=IntentType.GENERATE_CI_PIPELINE,
                target_agent=ChildAgentType.CI,
                confidence=0.92,
                entities={"pipeline_type": "ci"},
                reasoning="CI pipeline intent detected from deployment workflow request.",
            )

        if any(token in normalized for token in ["cd", "deploy pipeline", "release pipeline", "continuous deployment"]):
            return ClassifiedIntent(
                intent=IntentType.GENERATE_CD_PIPELINE,
                target_agent=ChildAgentType.CD,
                confidence=0.92,
                entities={"pipeline_type": "cd"},
                reasoning="CD pipeline intent detected from deployment workflow request.",
            )

        if any(token in normalized for token in ["help", "what can you do", "capabilities"]):
            return ClassifiedIntent(
                intent=IntentType.GENERAL_QUESTION,
                target_agent=ChildAgentType.UNKNOWN,
                confidence=0.8,
                reasoning="General help request detected.",
            )

        return ClassifiedIntent(
            intent=IntentType.UNKNOWN,
            target_agent=ChildAgentType.UNKNOWN,
            confidence=0.35,
            requires_clarification=True,
            clarification_question="I can generate a CI pipeline right now. Do you want me to proceed with the CI flow?",
            reasoning="Unable to clearly classify deployment request.",
        )


_classifier: IntentClassifier | None = None


def get_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier