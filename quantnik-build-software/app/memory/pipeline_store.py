"""
In-memory pipeline run store.
Keyed by run_id. In production, swap for Redis or Postgres.
"""
from typing import Dict, Optional
from app.models.responses import PipelineRun


_store: Dict[str, PipelineRun] = {}


def save(run: PipelineRun):
    _store[run.run_id] = run


def get(run_id: str) -> Optional[PipelineRun]:
    return _store.get(run_id)


def all_runs() -> Dict[str, PipelineRun]:
    return dict(_store)
