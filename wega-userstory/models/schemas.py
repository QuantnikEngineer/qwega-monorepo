"""Pydantic models for request/response payloads.

All user-supplied strings that flow through to Jira are validated for:
- presence (non-empty / non-whitespace),
- minimum length where it matters,
- correct Jira issue key format ``PROJECTKEY-123``.

These constraints turn a whole class of "garbage propagated to Jira" bugs
into clean 422 responses.
"""

import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


_JIRA_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")


def _normalize_jira_key(value: str) -> str:
    """Trim and uppercase a Jira key, rejecting interior whitespace."""
    if not isinstance(value, str):
        raise ValueError("Jira issue key must be a string")
    cleaned = value.strip().upper()
    if not cleaned:
        raise ValueError("Jira issue key must not be empty")
    if any(ch.isspace() for ch in cleaned):
        raise ValueError(
            f"Jira issue key '{value}' contains whitespace. "
            "Expected format: PROJECTKEY-123 (e.g. WEGAAIDEMO-17557)."
        )
    if not _JIRA_KEY_RE.match(cleaned):
        raise ValueError(
            f"Invalid Jira issue key format: '{value}'. "
            "Expected format: PROJECTKEY-123 (e.g. WEGAAIDEMO-17557)."
        )
    return cleaned


def _non_empty_text(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty or whitespace")
    return value  # preserve caller's original whitespace; just validated presence


def _validate_confluence_link(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("brd_confluence_link must not be empty")
    if any(ord(ch) < 32 for ch in value):
        raise ValueError("brd_confluence_link contains control characters")
    return value


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    deduped: List[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


class AcceptanceCriteria(BaseModel):
    criterion: str = Field(min_length=1)

    @field_validator("criterion")
    @classmethod
    def _validate_criterion(cls, v: str) -> str:
        return _non_empty_text(v, "acceptance_criteria.criterion")


# Valid Jira priority values (case-insensitive input accepted)
_VALID_PRIORITIES = {"highest", "high", "medium", "low", "lowest"}


class SubTask(BaseModel):
    """A sub-task to be created under a user story."""

    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: str) -> str:
        return _non_empty_text(v, "sub_task.title")

class UserStory(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    acceptance_criteria: List[AcceptanceCriteria] = Field(min_length=1)
    priority: Optional[str] = Field(default="Medium")
    sub_tasks: Optional[List[SubTask]] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: str) -> str:
        return _non_empty_text(v, "title")

    @field_validator("description")
    @classmethod
    def _v_description(cls, v: str) -> str:
        return _non_empty_text(v, "description")

    @field_validator("priority")
    @classmethod
    def _v_priority(cls, v: Optional[str]) -> str:
        if v is None:
            return "Medium"
        normalized = v.strip().lower()
        if normalized not in _VALID_PRIORITIES:
            return "Medium"
        return normalized.capitalize()


class Epic(BaseModel):
    epic_title: str = Field(min_length=1, max_length=255)
    epic_description: Optional[str] = None
    user_stories: List[UserStory] = Field(min_length=1)

    @field_validator("epic_title")
    @classmethod
    def _v_epic_title(cls, v: str) -> str:
        return _non_empty_text(v, "epic_title")


class AgentOutput(BaseModel):
    epics: List[Epic]
    brd_confluence_link: Optional[str] = None
    brd_title: Optional[str] = None


class GenerateUserStoriesRequest(BaseModel):
    brd_confluence_link: str = Field(min_length=1, max_length=2048)

    @field_validator("brd_confluence_link")
    @classmethod
    def _v_link(cls, v: str) -> str:
        return _validate_confluence_link(v)


class AdditionalUserStory(BaseModel):
    """Payload for creating additional user stories under existing Jira epics."""

    epic_issue_key: str
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    acceptance_criteria: List[AcceptanceCriteria] = Field(min_length=1)
    priority: Optional[str] = Field(default="Medium")
    sub_tasks: Optional[List[SubTask]] = Field(default_factory=list)

    @field_validator("epic_issue_key")
    @classmethod
    def _v_epic_key(cls, v: str) -> str:
        return _normalize_jira_key(v)

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: str) -> str:
        return _non_empty_text(v, "title")

    @field_validator("description")
    @classmethod
    def _v_description(cls, v: str) -> str:
        return _non_empty_text(v, "description")

    @field_validator("priority")
    @classmethod
    def _v_priority(cls, v: Optional[str]) -> str:
        if v is None:
            return "Medium"
        normalized = v.strip().lower()
        if normalized not in _VALID_PRIORITIES:
            return "Medium"
        return normalized.capitalize()


class JiraIssueUpdate(BaseModel):
    """Payload for updating an existing Jira issue.

    At least one of ``summary`` / ``description`` must be provided and
    non-empty.  Empty strings are rejected to prevent silently corrupting
    Jira fields.

    Optional ``expected_summary`` / ``expected_description`` enable
    optimistic concurrency: the server compares the current Jira values
    against these expectations and returns a conflict if they differ.
    """

    issue_key: str
    summary: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, min_length=1)
    expected_summary: Optional[str] = None
    expected_description: Optional[str] = None

    @field_validator("issue_key")
    @classmethod
    def _v_issue_key(cls, v: str) -> str:
        return _normalize_jira_key(v)

    @field_validator("summary", "description")
    @classmethod
    def _v_non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("field must not be empty or whitespace if provided")
        return v

    @model_validator(mode="after")
    def _at_least_one_field(self):
        if self.summary is None and self.description is None:
            raise ValueError("Provide at least one of: summary, description")
        return self


# ---------------------------------------------------------------------------
# Brownfield — BRD update analysis
# ---------------------------------------------------------------------------

class BrownfieldAnalysisRequest(BaseModel):
    """Request payload for the /analyze-brd-updates endpoint."""

    brd_confluence_link: str = Field(min_length=1, max_length=2048)
    jira_epic_keys: List[str] = Field(min_length=1)

    @field_validator("brd_confluence_link")
    @classmethod
    def _v_link(cls, v: str) -> str:
        return _validate_confluence_link(v)

    @field_validator("jira_epic_keys")
    @classmethod
    def _v_epic_keys(cls, v: List[str]) -> List[str]:
        normalized = [_normalize_jira_key(k) for k in v]
        return _dedupe_preserve_order(normalized)


class StoryUpdateProposal(BaseModel):
    """A proposal to update an existing Jira story as a result of BRD changes."""

    issue_key: str
    current_title: Optional[str] = None
    new_title: str = Field(min_length=1, max_length=255)
    new_description: str = Field(min_length=1)
    new_acceptance_criteria: List[AcceptanceCriteria] = Field(min_length=1)
    change_reason: Optional[str] = None

    @field_validator("issue_key")
    @classmethod
    def _v_key(cls, v: str) -> str:
        return _normalize_jira_key(v)

    @field_validator("new_title")
    @classmethod
    def _v_title(cls, v: str) -> str:
        return _non_empty_text(v, "new_title")

    @field_validator("new_description")
    @classmethod
    def _v_description(cls, v: str) -> str:
        return _non_empty_text(v, "new_description")


class NewStoryProposal(BaseModel):
    """A proposal to create a new Jira story under an existing epic."""

    epic_issue_key: str
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    acceptance_criteria: List[AcceptanceCriteria] = Field(min_length=1)
    priority: Optional[str] = Field(default="Medium")
    sub_tasks: Optional[List[SubTask]] = Field(default_factory=list)
    reason: Optional[str] = None

    @field_validator("epic_issue_key")
    @classmethod
    def _v_epic_key(cls, v: str) -> str:
        return _normalize_jira_key(v)

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: str) -> str:
        return _non_empty_text(v, "title")

    @field_validator("description")
    @classmethod
    def _v_description(cls, v: str) -> str:
        return _non_empty_text(v, "description")

    @field_validator("priority")
    @classmethod
    def _v_priority(cls, v: Optional[str]) -> str:
        if v is None:
            return "Medium"
        normalized = v.strip().lower()
        if normalized not in _VALID_PRIORITIES:
            return "Medium"
        return normalized.capitalize()


class EpicUpdateProposal(BaseModel):
    """A proposal to update an existing Epic's description due to BRD changes."""

    issue_key: str
    current_epic_title: Optional[str] = None
    new_epic_description: str = Field(min_length=1)
    change_reason: Optional[str] = None

    @field_validator("issue_key")
    @classmethod
    def _v_key(cls, v: str) -> str:
        return _normalize_jira_key(v)

    @field_validator("new_epic_description")
    @classmethod
    def _v_description(cls, v: str) -> str:
        return _non_empty_text(v, "new_epic_description")


class EpicCreateProposal(BaseModel):
    """A proposal to create a brand-new Epic for a net-new BRD section."""

    epic_title: str = Field(min_length=1, max_length=255)
    epic_description: str = Field(min_length=1)
    user_stories: List[UserStory] = Field(min_length=1)
    reason: Optional[str] = None

    @field_validator("epic_title")
    @classmethod
    def _v_title(cls, v: str) -> str:
        return _non_empty_text(v, "epic_title")

    @field_validator("epic_description")
    @classmethod
    def _v_description(cls, v: str) -> str:
        return _non_empty_text(v, "epic_description")


class StoryDeletionReview(BaseModel):
    """A story that may be obsolete because its BRD requirement was removed."""

    issue_key: str
    title: str
    reason: str

    @field_validator("issue_key")
    @classmethod
    def _v_key(cls, v: str) -> str:
        return _normalize_jira_key(v)


class BrownfieldAnalysisResult(BaseModel):
    """Structured result returned by the brownfield agent."""

    no_changes: bool = False
    summary: str = ""
    epics_to_update: List[EpicUpdateProposal] = Field(default_factory=list)
    stories_to_update: List[StoryUpdateProposal] = Field(default_factory=list)
    new_stories: List[NewStoryProposal] = Field(default_factory=list)
    epics_to_create: List[EpicCreateProposal] = Field(default_factory=list)
    stories_to_review_for_deletion: List[StoryDeletionReview] = Field(default_factory=list)


class JiraEpicSummary(BaseModel):
    """Lightweight epic info returned by GET /jira-epics for the UI picker."""

    issue_key: str
    epic_title: str


class ApplyBrdUpdatesRequest(BaseModel):
    """Request body for POST /apply-brd-updates."""

    brd_confluence_link: Optional[str] = None
    epics_to_update: List[EpicUpdateProposal] = Field(default_factory=list)
    stories_to_update: List[StoryUpdateProposal] = Field(default_factory=list)
    new_stories: List[NewStoryProposal] = Field(default_factory=list)
    epics_to_create: List[EpicCreateProposal] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_duplicate_keys(self):
        epic_keys = [e.issue_key for e in self.epics_to_update]
        if len(epic_keys) != len(set(epic_keys)):
            raise ValueError(
                "epics_to_update contains duplicate issue_keys; each epic may "
                "appear at most once per request."
            )
        story_keys = [s.issue_key for s in self.stories_to_update]
        if len(story_keys) != len(set(story_keys)):
            raise ValueError(
                "stories_to_update contains duplicate issue_keys; each story "
                "may appear at most once per request."
            )
        return self


# ---------------------------------------------------------------------------
# Brownfield — BRD update analysis
# ---------------------------------------------------------------------------

class BrownfieldAnalysisRequest(BaseModel):
    """Request payload for the /analyze-brd-updates endpoint.

    Supply the Confluence URL for the updated BRD and the Jira epic keys
    whose stories should be fetched and compared against the new BRD.
    """

    brd_confluence_link: str
    jira_epic_keys: List[str]


class StoryUpdateProposal(BaseModel):
    """A proposal to update an existing Jira story as a result of BRD changes."""

    issue_key: str
    current_title: Optional[str] = None
    new_title: str
    new_description: str
    new_acceptance_criteria: List[AcceptanceCriteria]
    change_reason: Optional[str] = None


class NewStoryProposal(BaseModel):
    """A proposal to create a new Jira story under an existing epic."""

    epic_issue_key: str
    title: str
    description: str
    acceptance_criteria: List[AcceptanceCriteria]
    reason: Optional[str] = None


class EpicUpdateProposal(BaseModel):
    """A proposal to update an existing Epic's description due to BRD changes."""

    issue_key: str
    current_epic_title: Optional[str] = None
    new_epic_description: str
    change_reason: Optional[str] = None


class EpicCreateProposal(BaseModel):
    """A proposal to create a brand-new Epic for a net-new BRD section."""

    epic_title: str
    epic_description: str
    user_stories: List[UserStory]
    reason: Optional[str] = None


class StoryDeletionReview(BaseModel):
    """A story that may be obsolete because its BRD requirement was removed."""

    issue_key: str
    title: str
    reason: str


class BrownfieldAnalysisResult(BaseModel):
    """Structured result returned by /analyze-brd-updates."""

    no_changes: bool
    summary: str
    epics_to_update: List[EpicUpdateProposal]
    stories_to_update: List[StoryUpdateProposal]
    new_stories: List[NewStoryProposal]
    epics_to_create: List[EpicCreateProposal]
    stories_to_review_for_deletion: List[StoryDeletionReview]


class JiraEpicSummary(BaseModel):
    """Lightweight epic info returned by GET /jira-epics for the UI picker."""

    issue_key: str
    epic_title: str


class ApplyBrdUpdatesRequest(BaseModel):
    """Request body for POST /apply-brd-updates.

    Pass the relevant parts of the 'changes' object from /analyze-brd-updates.
    All lists are optional — only the supplied items are applied.
    The brd_confluence_link is embedded in any newly created epics so future
    brownfield analyses can find them.
    """

    brd_confluence_link: Optional[str] = None
    epics_to_update: List[EpicUpdateProposal] = []
    stories_to_update: List[StoryUpdateProposal] = []
    new_stories: List[NewStoryProposal] = []
    epics_to_create: List[EpicCreateProposal] = []


class JiraIssueDelete(BaseModel):
    """Payload for deleting one or more Jira issues."""

    issue_key: str
    delete_subtasks: Optional[bool] = False

    @field_validator("issue_key")
    @classmethod
    def _v_key(cls, v: str) -> str:
        return _normalize_jira_key(v)
