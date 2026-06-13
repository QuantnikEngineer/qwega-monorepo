from __future__ import annotations

import json
from pathlib import Path

from models.schemas import HistoricalStoryRecord


class HistoryLoader:
    """Load normalized historical stories from local JSON assets.

    The first implementation uses a synthetic backlog to make the estimator runnable
    without upstream orchestrators or live Jira and ADO connections.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    def load_synthetic_history(self) -> list[HistoricalStoryRecord]:
        history_path = self.data_dir / "synthetic_historical_backlog.json"
        raw_records = json.loads(history_path.read_text(encoding="utf-8"))
        return [HistoricalStoryRecord.model_validate(record) for record in raw_records]

    def load_sample_request(self) -> dict:
        sample_path = self.data_dir / "sample_estimation_request.json"
        return json.loads(sample_path.read_text(encoding="utf-8"))
