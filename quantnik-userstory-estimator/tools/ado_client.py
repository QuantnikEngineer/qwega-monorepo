from __future__ import annotations

from models.schemas import HistoricalStoryRecord


class AzureDevOpsClient:
    """Enterprise integration placeholder for Azure DevOps.

    The first implementation keeps the interface explicit even though live ADO calls are not
    required for local direct-payload estimation.
    """

    def fetch_historical_stories(self) -> list[HistoricalStoryRecord]:
        return []
