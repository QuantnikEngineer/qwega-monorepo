from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from app.models.feedback import FeedbackType


class FeedbackRequest(BaseModel):
    feedback_type: FeedbackType

    # Required only for rating
    rating:        Optional[Literal["positive", "negative"]] = None

    # Required for correction / domain_preference
    content:       Optional[str] = None

    # Context — helps route the feedback to the right phase/agent
    artifact_type: Optional[str] = None   # brd | user_story | test_case | design …
    sdlc_phase:    Optional[str] = None
    agent_name:    Optional[str] = None
    session_id:    Optional[str] = None
    ref_doc_id:    Optional[UUID] = None  # ID of the document / agent output being rated

    @model_validator(mode="after")
    def validate_fields(self) -> "FeedbackRequest":
        if self.feedback_type == FeedbackType.RATING:
            if self.rating is None:
                raise ValueError("rating ('positive' or 'negative') is required for feedback_type='rating'")

        if self.feedback_type in (FeedbackType.CORRECTION, FeedbackType.DOMAIN_PREFERENCE):
            if not self.content or not self.content.strip():
                raise ValueError(
                    "content is required for feedback_type='correction' and 'domain_preference'"
                )

        return self


class FeedbackResponse(BaseModel):
    id:            UUID
    feedback_type: FeedbackType
    indexed:       bool
    message:       str
