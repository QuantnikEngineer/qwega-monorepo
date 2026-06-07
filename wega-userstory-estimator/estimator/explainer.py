from __future__ import annotations

from dataclasses import dataclass, field

from models.schemas import SimilarStoryReference, StoryInput


@dataclass(slots=True)
class ExplanationResult:
    rationale: str
    clarifying_questions: list[str] = field(default_factory=list)


class DeterministicExplainer:
    """Fallback explainer used when Gemini is disabled or unavailable.

    The service must remain fully functional without live model credentials, so this fallback
    produces consistent, reviewable explanations derived from the scoring evidence.
    """

    def explain(
        self,
        story: StoryInput,
        estimate: int,
        confidence: str,
        confidence_score: float,
        similar_stories: list[SimilarStoryReference],
        flags: list[str],
        historical_anchor: float | None,
        model_expected_points: float,
    ) -> ExplanationResult:
        context_bits: list[str] = []
        if historical_anchor is not None:
            context_bits.append(f"historical anchor {historical_anchor:.1f}")
        context_bits.append(f"model expectation {model_expected_points:.1f}")
        if similar_stories:
            context_bits.append(f"{len(similar_stories)} similar references")

        rationale = (
            f"'{story.title}' was estimated at {estimate} story points with {confidence.lower()} confidence "
            f"({confidence_score:.0%}) based on {', '.join(context_bits)}. "
            f"The scoring considered story size, acceptance-criteria completeness, technical keywords, and historical pattern matching."
        )
        if flags:
            rationale += f" Key watch items: {', '.join(flags[:3])}."

        clarifying_questions: list[str] = []
        if confidence != "HIGH":
            clarifying_questions.append("Are there any hidden integration or dependency requirements not stated in the story?")
        if not story.acceptance_criteria:
            clarifying_questions.append("Can the team add concrete Given/When/Then acceptance criteria before planning?" )

        return ExplanationResult(rationale=rationale, clarifying_questions=clarifying_questions)
