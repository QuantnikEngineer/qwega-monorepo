from __future__ import annotations

from models.schemas import HistoricalStoryRecord


class JiraClient:
    """Enterprise integration placeholder for Jira.

    The local estimator accepts direct stories and synthetic history because the upstream
    orchestrators are not running on this machine. This client is kept as a clean extension
    point for future live Jira fetch and writeback integration.
    """

    def fetch_historical_stories(self) -> list[HistoricalStoryRecord]:
        return []
