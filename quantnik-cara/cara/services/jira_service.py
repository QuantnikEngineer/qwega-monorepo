import json
import re
from typing import Any

from cara.core.errors import ExternalServiceError
from cara.models.domain import JiraIssueContext, JiraValidationResult, JiraValidationStatus


class JiraService:
    ISSUE_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

    def __init__(self, client: Any | None) -> None:
        self._client = client

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def extract_issue_key(self, *texts: str | None) -> str | None:
        for text in texts:
            if text is None:
                continue
            match = self.ISSUE_KEY_PATTERN.search(text)
            if match is not None:
                return match.group(1)
        return None

    def get_issue_context(self, issue_key: str) -> JiraIssueContext:
        if self._client is None:
            raise ExternalServiceError(
                "Jira validation requested without a configured Jira client.",
            )

        try:
            issue = self._client.issue(issue_key)
        except Exception as exc:
            raise ExternalServiceError(f"Unable to fetch Jira issue {issue_key}.") from exc

        fields = issue.fields
        description = self._coerce_text(getattr(fields, "description", None))
        status = getattr(getattr(fields, "status", None), "name", None)
        return JiraIssueContext(
            issue_key=issue_key,
            summary=str(getattr(fields, "summary", issue_key)),
            description=description,
            status=status,
            acceptance_criteria=self._extract_acceptance_criteria(description),
        )

    def build_not_evaluated_result(
        self,
        issue_key: str,
        reason: str,
    ) -> JiraValidationResult:
        return JiraValidationResult(
            issue_key=issue_key,
            status=JiraValidationStatus.NOT_EVALUATED,
            summary=reason,
            uncovered_requirements=[],
        )

    def _coerce_text(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _extract_acceptance_criteria(self, description: str | None) -> list[str]:
        if not description:
            return []

        lines = [line.strip() for line in description.splitlines() if line.strip()]
        criteria: list[str] = []
        capture = False

        for line in lines:
            lowered = line.lower().rstrip(":")
            if "acceptance criteria" in lowered:
                capture = True
                continue

            if capture and lowered.endswith(":") and "acceptance criteria" not in lowered:
                break

            if capture:
                criteria.append(line.lstrip("-* "))

        return criteria
