from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from estimator.explainer import DeterministicExplainer, ExplanationResult
from models.schemas import SimilarStoryReference, StoryInput

logger = logging.getLogger(__name__)

try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part
except Exception:  # noqa: BLE001
    Agent = None
    Runner = None
    InMemorySessionService = None
    Content = None
    Part = None


@dataclass(slots=True)
class ExplanationRequest:
    story: StoryInput
    estimate: int
    confidence: str
    confidence_score: float
    flags: list[str]
    historical_anchor: float | None
    model_expected_points: float
    similar_stories: list[SimilarStoryReference]


class EnterpriseExplainer:
    """Use Gemini ADK when available, otherwise fall back to deterministic explanations."""

    def __init__(self) -> None:
        self.gemini_enabled = bool(os.getenv("ENABLE_GEMINI_EXPLANATIONS", "false").lower() == "true")
        self.model_name = os.getenv("GEMINI_MODEL", "")
        self._fallback = DeterministicExplainer()
        self._root_agent = None
        if self.gemini_enabled and Agent and self.model_name:
            self._root_agent = Agent(
                name="story_estimator_explainer",
                model=self.model_name,
                description="Explains already-computed story point estimates without changing the score.",
                instruction=(
                    "You are an enterprise agile estimation explainer. You receive an already-computed "
                    "story point estimate, supporting evidence, similar stories, and flags. Respond with "
                    "a single JSON object containing rationale and clarifying_questions. Do not change the estimate."
                ),
                tools=[],
            )

    async def explain(self, request: ExplanationRequest) -> ExplanationResult:
        if not self.gemini_enabled or not self._root_agent or not Runner or not InMemorySessionService:
            return self._fallback.explain(
                story=request.story,
                estimate=request.estimate,
                confidence=request.confidence,
                confidence_score=request.confidence_score,
                similar_stories=request.similar_stories,
                flags=request.flags,
                historical_anchor=request.historical_anchor,
                model_expected_points=request.model_expected_points,
            )

        try:
            payload = {
                "story": {
                    "title": request.story.title,
                    "description": request.story.description,
                    "acceptance_criteria": [item.criterion for item in request.story.acceptance_criteria],
                },
                "estimate": request.estimate,
                "confidence": request.confidence,
                "confidence_score": request.confidence_score,
                "flags": request.flags,
                "historical_anchor": request.historical_anchor,
                "model_expected_points": request.model_expected_points,
                "similar_stories": [item.model_dump() for item in request.similar_stories],
            }

            session_service = InMemorySessionService()
            runner = Runner(agent=self._root_agent, session_service=session_service, app_name="story_estimator_explainer")
            session = await session_service.create_session(app_name="story_estimator_explainer", user_id="api_user")
            final_text = ""
            async for event in runner.run_async(
                user_id="api_user",
                session_id=session.id,
                new_message=Content(role="user", parts=[Part(text=json.dumps(payload))]),
            ):
                if event.is_final_response() and event.content:
                    final_text = "".join(part.text for part in event.content.parts if getattr(part, "text", None))

            parsed = json.loads(final_text)
            return ExplanationResult(
                rationale=parsed.get("rationale", "The estimate was produced from retrieval, model scoring, and rules."),
                clarifying_questions=parsed.get("clarifying_questions", []),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini explanation failed, using fallback: %s", exc)
            return self._fallback.explain(
                story=request.story,
                estimate=request.estimate,
                confidence=request.confidence,
                confidence_score=request.confidence_score,
                similar_stories=request.similar_stories,
                flags=request.flags,
                historical_anchor=request.historical_anchor,
                model_expected_points=request.model_expected_points,
            )
