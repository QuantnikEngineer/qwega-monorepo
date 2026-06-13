from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AcceptanceCriteria(BaseModel):
    """A single acceptance criterion for an incoming or historical user story."""

    criterion: str = Field(..., min_length=1)


class StoryInput(BaseModel):
    """Direct story payload accepted by the estimator service.

    The orchestrators are not available locally, so the service accepts stories directly
    instead of relying on upstream workflow state.
    """

    story_id: str | None = None
    epic_id: str | None = None
    epic_title: str | None = None
    title: str = Field(..., min_length=3)
    description: str = Field(..., min_length=10)
    acceptance_criteria: list[AcceptanceCriteria] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    team_id: str | None = None
    source: Literal["direct", "jira", "ado"] = "direct"


class EpicInput(BaseModel):
    """A direct epic payload with nested stories to estimate."""

    epic_id: str | None = None
    epic_title: str = Field(..., min_length=3)
    epic_description: str | None = None
    team_id: str | None = None
    user_stories: list[StoryInput] = Field(default_factory=list)


class EstimateStoriesRequest(BaseModel):
    """Direct estimation request for local development and API usage."""

    epics: list[EpicInput] = Field(default_factory=list)
    stories: list[StoryInput] = Field(default_factory=list)
    include_similar_stories: bool = True
    use_gemini_explanations: bool = True
    top_k_similar: int = Field(default=5, ge=1, le=10)

    @model_validator(mode="after")
    def validate_has_story_input(self) -> "EstimateStoriesRequest":
        if not self.epics and not self.stories:
            raise ValueError("Provide at least one epic or one story for estimation.")
        return self


class HistoricalStoryRecord(BaseModel):
    """Normalized historical story record used for retrieval and model training."""

    story_id: str
    epic_title: str
    title: str
    description: str
    acceptance_criteria: list[AcceptanceCriteria] = Field(default_factory=list)
    story_points: int = Field(..., ge=1)
    sprint: str | None = None
    team_id: str | None = None
    actual_effort_hours: float | None = None
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    source: Literal["synthetic", "jira", "ado", "idp"] = "synthetic"


class SimilarStoryReference(BaseModel):
    """Returned historical story reference used to justify the estimate."""

    story_id: str
    epic_title: str
    title: str
    story_points: int
    similarity_score: float = Field(..., ge=0.0, le=1.0)


class EstimationBreakdown(BaseModel):
    """Transparent view of how the final estimate was formed."""

    historical_anchor: float | None = None
    ml_expected_points: float
    rule_adjustment: float
    final_numeric_score: float
    model_accuracy: float
    model_version: str


class EstimatedStory(BaseModel):
    """Story output returned by the estimator service."""

    story_id: str
    epic_title: str
    title: str
    description: str
    acceptance_criteria: list[AcceptanceCriteria] = Field(default_factory=list)
    estimated_story_points: int
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    point_range: list[int] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    rationale: str
    clarifying_questions: list[str] = Field(default_factory=list)
    similar_stories: list[SimilarStoryReference] = Field(default_factory=list)
    breakdown: EstimationBreakdown


class EstimatedEpic(BaseModel):
    """Epic output returned by the estimator service."""

    epic_title: str
    epic_description: str | None = None
    user_stories: list[EstimatedStory] = Field(default_factory=list)


class EstimateStoriesResponse(BaseModel):
    """Top-level response returned by the estimator endpoint."""

    status: Literal["success"]
    summary: str
    epics: list[EstimatedEpic] = Field(default_factory=list)
    stories: list[EstimatedStory] = Field(default_factory=list)
    synthetic_history_used: bool = True
    model_version: str


class HealthResponse(BaseModel):
    """Simple health endpoint response."""

    status: Literal["healthy"]
    service: str
    model_version: str
    synthetic_history_enabled: bool
    gemini_explanations_enabled: bool
