"""Generic dataset manager — agent-agnostic."""

from __future__ import annotations

import logging
from typing import Any

from langfuse import Langfuse

from quantnik_evals.agent_profile import AgentProfile
from quantnik_evals.config import EvalConfig
from quantnik_evals.llm_judge import build_langfuse_httpx_client
from quantnik_evals.models import DatasetItem

logger = logging.getLogger(__name__)


class DatasetManager:
    """Create and manage Langfuse datasets for any agent."""

    def __init__(self, config: EvalConfig, profile: AgentProfile) -> None:
        self._config = config
        self._profile = profile
        self._lf = Langfuse(
            public_key=config.langfuse_public_key,
            secret_key=config.langfuse_secret_key,
            host=config.langfuse_host,
            httpx_client=build_langfuse_httpx_client(),
        )

    # ------------------------------------------------------------------
    # Seed from existing traces
    # ------------------------------------------------------------------

    def seed_from_traces(
        self,
        *,
        trace_name: str | None = None,
        limit: int = 20,
        min_observations: int = 2,
    ) -> list[DatasetItem]:
        """Pull traces and convert them into dataset items.

        Uses the agent profile's trace_name and extract_input/output
        methods to build items.
        """
        name = trace_name or self._profile.trace_name
        if not name:
            raise ValueError("trace_name must be set on the agent profile or passed explicitly")

        traces = self._lf.api.trace.list(name=name, limit=limit)
        items: list[DatasetItem] = []

        for trace in traces.data:
            full_trace = self._lf.api.trace.get(trace.id)
            observations = full_trace.observations or []
            if len(observations) < min_observations:
                logger.debug("Skipping trace %s — only %d observations",
                             trace.id, len(observations))
                continue

            input_data = self._profile.extract_input(full_trace, observations)
            output_data = self._profile.extract_output(full_trace, observations)

            item = DatasetItem(
                id=trace.id,
                input=input_data,
                expected_output=output_data,
                metadata={
                    "source": "langfuse_trace",
                    "agent": self._profile.name,
                    "trace_timestamp": (
                        trace.timestamp.isoformat() if trace.timestamp else ""
                    ),
                    "total_observations": len(observations),
                },
                trace_id=trace.id,
            )
            items.append(item)

        logger.info("Seeded %d items from %d '%s' traces",
                     len(items), len(traces.data), name)
        return items

    # ------------------------------------------------------------------
    # Push / load
    # ------------------------------------------------------------------

    def push_dataset(
        self,
        items: list[DatasetItem],
        dataset_name: str | None = None,
        description: str = "",
    ) -> str:
        """Create/update a Langfuse dataset."""
        name = dataset_name or self._config.dataset_name or self._profile.default_dataset
        self._lf.create_dataset(
            name=name,
            description=description or f"{self._profile.name} eval dataset ({len(items)} items)",
        )
        for item in items:
            self._lf.create_dataset_item(
                dataset_name=name,
                input=item.input,
                expected_output=item.expected_output,
                metadata=item.metadata,
                id=item.id,
            )
        logger.info("Pushed %d items to dataset '%s'", len(items), name)
        return name

    def load_dataset(self, dataset_name: str | None = None) -> list[DatasetItem]:
        """Load dataset items from Langfuse."""
        name = dataset_name or self._config.dataset_name or self._profile.default_dataset
        ds = self._lf.get_dataset(name)
        items = []
        for lf_item in ds.items:
            # trace_id: try metadata["trace_id"], then fall back to item ID
            # (seeder uses trace.id as the dataset-item id)
            tid = (
                lf_item.metadata.get("trace_id")
                if lf_item.metadata else None
            ) or lf_item.id
            items.append(DatasetItem(
                id=lf_item.id,
                input=lf_item.input or {},
                expected_output=lf_item.expected_output,
                metadata=lf_item.metadata or {},
                trace_id=tid,
            ))
        return items

    # ------------------------------------------------------------------
    # Manual item creation
    # ------------------------------------------------------------------

    def add_item(
        self,
        *,
        input_data: dict[str, Any],
        expected_output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        item_id: str | None = None,
        dataset_name: str | None = None,
    ) -> DatasetItem:
        """Add a manually curated evaluation item."""
        name = dataset_name or self._config.dataset_name or self._profile.default_dataset
        iid = item_id or f"{self._profile.name}-manual-{len(self.load_dataset(name)) + 1}"

        item = DatasetItem(
            id=iid,
            input=input_data,
            expected_output=expected_output,
            metadata=metadata or {"source": "manual", "agent": self._profile.name},
        )

        self._lf.create_dataset_item(
            dataset_name=name,
            input=item.input,
            expected_output=item.expected_output,
            metadata=item.metadata,
            id=item.id,
        )
        return item
