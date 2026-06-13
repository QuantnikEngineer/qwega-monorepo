from pydantic import BaseModel, Field

from cara.models.domain import JiraValidationResult, ReviewIssueType, ReviewOverallStatus


class StructuredReviewFinding(BaseModel):
    file_path: str = Field(min_length=1)
    line_number: int = Field(ge=1)
    issue_type: ReviewIssueType
    severity_score: int = Field(ge=1, le=10)
    comment: str = Field(min_length=1)
    cwe_identifier: str | None = None
    suggested_remediation_code: str = Field(min_length=1)


class StructuredReviewAssessment(BaseModel):
    overall_status: ReviewOverallStatus
    summary: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    vulnerabilities_and_bugs: list[StructuredReviewFinding]
    jira_validation: JiraValidationResult | None = None
