from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RegistrationResult:
    story_id: str
    registered: bool
    message: str


class RegistrationService:
    """Placeholder registration service.

    Local development runs without orchestrators or live source-system credentials, so the
    default implementation is intentionally safe and non-destructive. It provides a clear
    extension point for Jira and Azure DevOps writeback when production integration is enabled.
    """

    def register_story_points(self, story_id: str, story_points: int) -> RegistrationResult:
        return RegistrationResult(
            story_id=story_id,
            registered=False,
            message=(
                f"Registration skipped for {story_id}. Local mode estimated {story_points} points "
                "without writing back to an external system."
            ),
        )
