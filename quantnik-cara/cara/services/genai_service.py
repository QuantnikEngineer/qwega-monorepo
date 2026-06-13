import logging
import mimetypes
import textwrap
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from cara.core.config import Settings
from cara.core.errors import BadRequestError, ExternalServiceError
from cara.models.domain import (
    JiraIssueContext,
    PromptScanReference,
    PullRequestContext,
    RepositoryScanContext,
    ReviewAssessment,
    ReviewFinding,
    ReviewFindingCategory,
    ReviewIssueType,
    ReviewSeverity,
)
from cara.models.schemas import StructuredReviewAssessment, StructuredReviewFinding

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

_KNOWN_TEXT_FILENAMES = {
    "dockerfile": "text/plain",
    "makefile": "text/plain",
    "license": "text/plain",
    "readme": "text/plain",
}

_GEMINI_SUPPORTED_MIME_TYPES = {
    "text/plain",
    "text/html",
    "text/css",
    "text/javascript",
    "text/x-python",
    "text/markdown",
    "text/csv",
    "text/xml",
    "text/rtf",
    "application/json",
    "application/pdf",
}


@dataclass(slots=True)
class UploadedContextFile:
    path: str
    uri: str
    mime_type: str
    handle: Any


class GenAIService:
    def __init__(self, client: Any, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def extract_pull_request_reference(self, command: str) -> PromptScanReference:
        try:
            from google.genai import types
        except ImportError as exc:
            raise ExternalServiceError("google-genai is unavailable for prompt parsing.") from exc

        response = self._client.models.generate_content(
            model=self._settings.llm_model_fast,
            contents=[
                textwrap.dedent(
                    f"""
                    Extract the repository owner, repository name, hosting provider and
                    (optionally) pull request number, branch/tag/commit reference, and
                    folder filter from the user command below.

                    Rules:
                    - owner and repo are required.
                    - provider is one of "github" or "harness".
                      * github when the URL contains github.com or no provider hint is given.
                      * harness when the URL or text mentions Harness Code, git.harness.io,
                        or app.harness.io paths under /code/ or /repos/.
                      * For Harness URLs of the form
                        https://git.harness.io/<account>/<org>/<project>/<repo> or
                        https://app.harness.io/ng/account/<id>/code/orgs/<org>/projects/<proj>/repos/<repo>,
                        set owner = "<org>/<project>" (use "/" as separator) and
                        repo = "<repo>".
                    - pr_number is optional; if the user does not mention a pull request,
                      set it to 0.
                    - ref is optional; populate it only when the user names a branch, tag,
                      or commit SHA.
                    - folder is optional; populate it only when the user restricts the
                      scan to a specific folder (e.g. 'src', 'app/api'). Use a relative
                      POSIX path with no leading slash.

                    Return JSON only.

                    User command:
                    {command}
                    """,
                ).strip(),
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=PromptScanReference,
            ),
        )
        reference = self._parse_response_model(response, PromptScanReference)

        # Override provider with a deterministic URL-pattern check so a Harness
        # URL is never silently misclassified as GitHub when the LLM gets it
        # wrong (defence-in-depth against prompt-injection too).
        from cara.services.repo_provider_factory import detect_provider_from_text

        detected = detect_provider_from_text(command)
        if reference.provider != detected:
            reference = reference.model_copy(update={"provider": detected})

        logger.info(
            "prompt_extraction command=%r owner=%r repo=%r pr_number=%s ref=%r folder=%r provider=%s",
            command,
            reference.owner,
            reference.repo,
            reference.pr_number,
            reference.ref,
            reference.folder,
            reference.provider,
        )
        if not reference.owner or not reference.repo:
            raise BadRequestError(
                "Unable to extract repository owner and name from the prompt. "
                f"Got owner={reference.owner!r}, repo={reference.repo!r}. "
                "Please include them, e.g. 'Scan PR-11 of owner/repo' or "
                "'Scan the src folder of owner/repo'.",
            )
        return reference

    def upload_context_files(
        self,
        repository_root: Path,
        files: list[Path],
    ) -> list[UploadedContextFile]:
        if not files:
            return []

        def _upload_one(path: Path) -> UploadedContextFile:
            mime_type = self._guess_mime_type(path)
            try:
                uploaded_file = self._client.files.upload(
                    file=str(path),
                    config={"mime_type": mime_type},
                )
            except Exception as exc:
                raise ExternalServiceError(
                    f"Failed to upload context file {path}.",
                ) from exc

            uri = getattr(uploaded_file, "uri", None) or getattr(uploaded_file, "name", None)
            if uri is None:
                raise ExternalServiceError(
                    f"Google GenAI did not return a URI for {path}.",
                )

            effective_mime_type = getattr(uploaded_file, "mime_type", None) or mime_type
            return UploadedContextFile(
                path=path.relative_to(repository_root).as_posix(),
                uri=uri,
                mime_type=effective_mime_type,
                handle=uploaded_file,
            )

        workers = max(1, min(len(files), self._settings.upload_concurrency))
        if workers == 1:
            return [_upload_one(path) for path in files]

        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(_upload_one, files))

    def generate_review(
        self,
        pull_request: PullRequestContext,
        context_files: list[UploadedContextFile],
        jira_issue: JiraIssueContext | None,
    ) -> ReviewAssessment:
        try:
            from google.genai import types
        except ImportError as exc:
            raise ExternalServiceError(
                "google-genai is unavailable for review generation.",
            ) from exc

        context_manifest = (
            "\n".join(
                f"- {context_file.path} -> {context_file.uri}" for context_file in context_files
            )
            or "- No repository files were uploaded."
        )
        jira_section = self._build_jira_section(jira_issue)
        review_prompt = textwrap.dedent(
            f"""
            You are an automated AI code review agent.
            Review the pull request for security vulnerabilities, code quality issues,
            best-practice violations, and Jira requirement alignment when Jira context is supplied.
            Ground every finding in the changed code or the uploaded repository context.
            Use the repository context to reason carefully before responding.

            Return JSON only with the exact schema fields:
            - overall_status
            - summary
            - strengths
            - vulnerabilities_and_bugs
            - jira_validation

            For each item in vulnerabilities_and_bugs, provide:
            - file_path
            - line_number
            - issue_type (Security_Vulnerability, Bug, Missing_Best_Practice)
            - severity_score (integer 1-10)
            - comment
            - cwe_identifier (string or null)
            - suggested_remediation_code (exact syntactically correct code patch)

            If no issues are found, return an empty vulnerabilities_and_bugs array.

            Pull request metadata:
            - Repository: {pull_request.owner}/{pull_request.repo}
            - Pull Request Number: {pull_request.pr_number}
            - Title: {pull_request.title}
            - Base Branch: {pull_request.base_ref}
            - Head Branch: {pull_request.head_ref}
            - Head SHA: {pull_request.head_sha}
            - URL: {pull_request.html_url}

            Uploaded repository context files:
            {context_manifest}

            {jira_section}

            Unified diff:
            {self._truncate_diff(pull_request.diff)}

            Return JSON only and keep the response strictly aligned with the provided schema.
            """
        ).strip()

        contents: list[Any] = [
            review_prompt,
            *[context_file.handle for context_file in context_files],
        ]
        response = self._client.models.generate_content(
            model=self._settings.llm_model_reasoning,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=StructuredReviewAssessment,
            ),
        )
        structured_review = self._parse_response_model(response, StructuredReviewAssessment)
        return self._to_review_assessment(structured_review)

    def generate_repo_scan_review(
        self,
        scan_context: RepositoryScanContext,
        context_files: list[UploadedContextFile],
    ) -> ReviewAssessment:
        try:
            from google.genai import types
        except ImportError as exc:
            raise ExternalServiceError(
                "google-genai is unavailable for review generation.",
            ) from exc

        context_manifest = (
            "\n".join(
                f"- {context_file.path} -> {context_file.uri}" for context_file in context_files
            )
            or "- No repository files were uploaded."
        )
        folder_section = (
            f"Scan was restricted to the folder: {scan_context.folder}"
            if scan_context.folder
            else "Scan covered the full repository (no folder filter)."
        )

        review_prompt = textwrap.dedent(
            f"""
            You are an automated AI code review agent.
            You have been asked to perform a repository-level scan (no pull request diff).
            Review the uploaded repository context for security vulnerabilities, code
            quality issues, and best-practice violations. Ground every finding in the
            uploaded files.

            Return JSON only with the exact schema fields:
            - overall_status
            - summary
            - strengths
            - vulnerabilities_and_bugs
            - jira_validation (set to null for repository scans)

            For each item in vulnerabilities_and_bugs, provide:
            - file_path
            - line_number
            - issue_type (Security_Vulnerability, Bug, Missing_Best_Practice)
            - severity_score (integer 1-10)
            - comment
            - cwe_identifier (string or null)
            - suggested_remediation_code (exact syntactically correct code patch)

            If no issues are found, return an empty vulnerabilities_and_bugs array.

            Repository metadata:
            - Repository: {scan_context.owner}/{scan_context.repo}
            - Reference: {scan_context.ref}
            - Head SHA: {scan_context.head_sha}
            - URL: {scan_context.html_url}

            {folder_section}

            Uploaded repository context files:
            {context_manifest}

            Return JSON only and keep the response strictly aligned with the provided schema.
            """,
        ).strip()

        contents: list[Any] = [
            review_prompt,
            *[context_file.handle for context_file in context_files],
        ]
        response = self._client.models.generate_content(
            model=self._settings.llm_model_reasoning,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=StructuredReviewAssessment,
            ),
        )
        structured_review = self._parse_response_model(response, StructuredReviewAssessment)
        assessment = self._to_review_assessment(structured_review)
        assessment.jira_validation = None
        return assessment

    def _truncate_diff(self, diff: str) -> str:
        if len(diff) <= self._settings.max_diff_characters:
            return diff
        return (
            f"{diff[: self._settings.max_diff_characters]}\n\n"
            "[Diff truncated to respect the configured context limit.]"
        )

    def _build_jira_section(self, jira_issue: JiraIssueContext | None) -> str:
        if jira_issue is None:
            return "No Jira issue context was supplied."

        acceptance_criteria = "\n".join(
            f"- {criterion}" for criterion in jira_issue.acceptance_criteria
        )
        acceptance_criteria = (
            acceptance_criteria or "- No explicit acceptance criteria were parsed."
        )
        description = jira_issue.description or "No Jira description was available."

        return textwrap.dedent(
            f"""
            Jira issue context:
            - Issue Key: {jira_issue.issue_key}
            - Summary: {jira_issue.summary}
            - Status: {jira_issue.status or "Unknown"}
            - Description:
            {description}
            - Acceptance Criteria:
            {acceptance_criteria}
            """,
        ).strip()

    def _guess_mime_type(self, path: Path) -> str:
        name_lower = path.name.lower()
        if name_lower in _KNOWN_TEXT_FILENAMES:
            return _KNOWN_TEXT_FILENAMES[name_lower]
        if name_lower.startswith(".") and "." not in name_lower[1:]:
            return "text/plain"
        guessed_mime_type = mimetypes.guess_type(path.name)[0]
        if guessed_mime_type is None:
            return "text/plain"
        if guessed_mime_type in _GEMINI_SUPPORTED_MIME_TYPES:
            return guessed_mime_type
        return "text/plain"

    def _to_review_assessment(
        self,
        structured_review: StructuredReviewAssessment,
    ) -> ReviewAssessment:
        return ReviewAssessment(
            overall_status=structured_review.overall_status,
            summary=structured_review.summary,
            strengths=structured_review.strengths,
            findings=[
                self._to_review_finding(finding)
                for finding in structured_review.vulnerabilities_and_bugs
            ],
            jira_validation=structured_review.jira_validation,
        )

    def _to_review_finding(self, finding: StructuredReviewFinding) -> ReviewFinding:
        return ReviewFinding(
            title=self._build_finding_title(finding),
            severity=self._map_severity(finding.severity_score),
            category=self._map_issue_category(finding.issue_type),
            description=finding.comment,
            recommendation=(
                "Apply the suggested remediation code and add regression coverage "
                "for the affected path."
            ),
            file_path=finding.file_path,
            line_number=finding.line_number,
            issue_type=finding.issue_type,
            severity_score=finding.severity_score,
            comment=finding.comment,
            cwe_identifier=finding.cwe_identifier,
            suggested_remediation_code=finding.suggested_remediation_code,
        )

    def _build_finding_title(self, finding: StructuredReviewFinding) -> str:
        issue_label = finding.issue_type.value.replace("_", " ")
        location = f"{finding.file_path}:{finding.line_number}"
        if finding.cwe_identifier:
            return f"{issue_label} ({finding.cwe_identifier}) at {location}"
        return f"{issue_label} at {location}"

    def _map_issue_category(self, issue_type: ReviewIssueType) -> ReviewFindingCategory:
        if issue_type is ReviewIssueType.SECURITY_VULNERABILITY:
            return ReviewFindingCategory.SECURITY
        if issue_type is ReviewIssueType.BUG:
            return ReviewFindingCategory.QUALITY
        return ReviewFindingCategory.BEST_PRACTICE

    def _map_severity(self, severity_score: int) -> ReviewSeverity:
        if severity_score >= 9:
            return ReviewSeverity.CRITICAL
        if severity_score >= 7:
            return ReviewSeverity.HIGH
        if severity_score >= 4:
            return ReviewSeverity.MEDIUM
        if severity_score >= 2:
            return ReviewSeverity.LOW
        return ReviewSeverity.INFO

    def _parse_response_model(self, response: Any, model_type: type[ModelT]) -> ModelT:
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            if isinstance(parsed, model_type):
                return parsed
            return model_type.model_validate(parsed)

        response_text = getattr(response, "text", None)
        if not response_text:
            raise ExternalServiceError("Google GenAI returned an empty response.")

        try:
            return model_type.model_validate_json(response_text)
        except ValidationError as exc:
            raise ExternalServiceError(
                "Google GenAI returned an invalid structured response.",
            ) from exc
