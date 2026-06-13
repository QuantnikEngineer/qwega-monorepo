from __future__ import annotations

from dataclasses import dataclass, field

from models.schemas import StoryInput


@dataclass(slots=True)
class RuleResult:
    adjustment: float
    flags: list[str] = field(default_factory=list)
    clarifying_questions: list[str] = field(default_factory=list)


class RuleEngine:
    """Apply deterministic business heuristics to supplement the ML estimate."""

    def apply(self, story: StoryInput) -> RuleResult:
        text = self._story_to_text(story).lower()
        adjustment = 0.0
        flags: list[str] = []
        questions: list[str] = []

        if not story.acceptance_criteria:
            flags.append("Missing acceptance criteria")
            questions.append("What are the concrete acceptance criteria for this story?")
            adjustment += 0.5

        if "new microservice" in text or "new service" in text:
            adjustment += 2.0
            flags.append("New service introduction")

        if "ui redesign" in text or "redesign" in text:
            adjustment += 1.0
            flags.append("UI redesign")

        integration_count = sum(
            keyword in text
            for keyword in ["api", "integration", "webhook", "partner", "vendor", "external"]
        )
        if integration_count >= 3:
            adjustment += 2.0
            flags.append("Multiple integration touchpoints")

        if any(keyword in text for keyword in ["migration", "schema", "backfill"]):
            adjustment += 1.5
            flags.append("Data migration or schema change")

        if any(keyword in text for keyword in ["oauth", "permission", "auth", "token"]):
            adjustment += 1.0
            flags.append("Security or access-control impact")

        if len(self._story_to_text(story).split()) > 120:
            flags.append("Consider splitting this story")
            questions.append("Can this story be split into smaller independently shippable slices?")

        return RuleResult(adjustment=round(adjustment, 2), flags=flags, clarifying_questions=questions)

    @staticmethod
    def _story_to_text(story: StoryInput) -> str:
        criteria = " ".join(item.criterion for item in story.acceptance_criteria)
        return f"{story.title} {story.description} {criteria}".strip()
