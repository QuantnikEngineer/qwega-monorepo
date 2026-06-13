from __future__ import annotations

from dataclasses import dataclass

from models.schemas import StoryInput


INTEGRATION_KEYWORDS = {"api", "webhook", "integration", "sync", "gateway", "service"}
DATABASE_KEYWORDS = {"database", "schema", "migration", "query", "table", "index"}
SECURITY_KEYWORDS = {"auth", "oauth", "token", "permission", "security", "role", "access"}
UI_KEYWORDS = {"ui", "screen", "page", "form", "dashboard", "filter", "button"}
REPORTING_KEYWORDS = {"report", "export", "csv", "analytics", "metric", "insight"}
ASYNC_KEYWORDS = {"async", "queue", "job", "retry", "event", "notification", "background"}
DEPENDENCY_KEYWORDS = {"third-party", "vendor", "external", "dependency", "partner"}
TESTING_KEYWORDS = {"test", "validation", "qa", "regression", "acceptance"}


@dataclass(slots=True)
class FeatureSnapshot:
    word_count: float
    title_word_count: float
    acceptance_criteria_count: float
    average_criterion_length: float
    integration_hits: float
    database_hits: float
    security_hits: float
    ui_hits: float
    reporting_hits: float
    async_hits: float
    dependency_hits: float
    testing_hits: float
    complexity_score: float

    def to_vector(self) -> list[float]:
        return [
            self.word_count,
            self.title_word_count,
            self.acceptance_criteria_count,
            self.average_criterion_length,
            self.integration_hits,
            self.database_hits,
            self.security_hits,
            self.ui_hits,
            self.reporting_hits,
            self.async_hits,
            self.dependency_hits,
            self.testing_hits,
            self.complexity_score,
        ]


class FeatureExtractor:
    """Create deterministic model features from a story payload.

    The feature set intentionally stays transparent and stable so that onboarding engineers
    and auditors can reason about how the ML input is formed.
    """

    def extract(self, story: StoryInput) -> FeatureSnapshot:
        full_text = self.story_to_text(story).lower()
        words = [token for token in full_text.replace("\n", " ").split() if token]
        title_words = [token for token in story.title.lower().split() if token]
        criteria_texts = [item.criterion.lower() for item in story.acceptance_criteria]
        average_criterion_length = (
            sum(len(item.split()) for item in criteria_texts) / len(criteria_texts)
            if criteria_texts
            else 0.0
        )

        integration_hits = self._count_keyword_hits(words, INTEGRATION_KEYWORDS)
        database_hits = self._count_keyword_hits(words, DATABASE_KEYWORDS)
        security_hits = self._count_keyword_hits(words, SECURITY_KEYWORDS)
        ui_hits = self._count_keyword_hits(words, UI_KEYWORDS)
        reporting_hits = self._count_keyword_hits(words, REPORTING_KEYWORDS)
        async_hits = self._count_keyword_hits(words, ASYNC_KEYWORDS)
        dependency_hits = self._count_keyword_hits(words, DEPENDENCY_KEYWORDS)
        testing_hits = self._count_keyword_hits(words, TESTING_KEYWORDS)

        complexity_score = (
            1.0
            + integration_hits * 0.6
            + database_hits * 0.7
            + security_hits * 0.8
            + ui_hits * 0.4
            + reporting_hits * 0.5
            + async_hits * 0.7
            + dependency_hits * 0.8
        )

        return FeatureSnapshot(
            word_count=float(len(words)),
            title_word_count=float(len(title_words)),
            acceptance_criteria_count=float(len(criteria_texts)),
            average_criterion_length=float(round(average_criterion_length, 2)),
            integration_hits=float(integration_hits),
            database_hits=float(database_hits),
            security_hits=float(security_hits),
            ui_hits=float(ui_hits),
            reporting_hits=float(reporting_hits),
            async_hits=float(async_hits),
            dependency_hits=float(dependency_hits),
            testing_hits=float(testing_hits),
            complexity_score=float(round(complexity_score, 2)),
        )

    @staticmethod
    def story_to_text(story: StoryInput) -> str:
        criteria = " ".join(item.criterion for item in story.acceptance_criteria)
        return f"{story.title} {story.description} {criteria}".strip()

    @staticmethod
    def _count_keyword_hits(words: list[str], keywords: set[str]) -> int:
        return sum(1 for word in words if any(keyword in word for keyword in keywords))
