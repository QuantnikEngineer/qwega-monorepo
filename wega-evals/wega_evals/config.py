"""Framework configuration — agent-agnostic."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class EvalConfig:
    """Configuration for an evaluation run."""

    # --- Langfuse connection ---
    langfuse_public_key: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_PUBLIC_KEY", ""),
    )
    langfuse_secret_key: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_SECRET_KEY", ""),
    )
    langfuse_host: str = field(
        default_factory=lambda: os.getenv("LANGFUSE_HOST", ""),
    )

    # --- Judge model ---
    judge_model: str = field(
        default_factory=lambda: os.getenv("JUDGE_MODEL", "gemini-2.5-pro"),
    )
    judge_temperature: float = 0.0

    # --- Vertex AI (default) ---
    judge_use_vertex: bool = field(
        default_factory=lambda: os.getenv("JUDGE_USE_VERTEX", "true").lower() == "true",
    )
    vertex_project: str = field(
        default_factory=lambda: os.getenv("VERTEX_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "")),
    )
    vertex_location: str = field(
        default_factory=lambda: os.getenv("VERTEX_LOCATION", "us-central1"),
    )

    # --- Google AI API key (alternative to Vertex) ---
    judge_api_key: str = field(
        default_factory=lambda: os.getenv("JUDGE_API_KEY", os.getenv("GOOGLE_API_KEY", "")),
    )

    # --- Run settings ---
    dataset_name: str = ""             # Override per agent profile
    run_name: str = ""                 # Auto-generated if empty

    # --- SSL / proxy ---
    ca_cert_path: str = field(
        default_factory=lambda: os.getenv("SSL_CERT_FILE", ""),
    )

    # --- Concurrency ---
    max_workers: int = field(
        default_factory=lambda: int(os.getenv("EVAL_MAX_WORKERS", "4")),
    )
    max_dim_workers: int = field(
        default_factory=lambda: int(os.getenv("EVAL_MAX_DIM_WORKERS", "8")),
    )

    # --- Scoring ---
    pass_threshold: float = field(
        default_factory=lambda: float(os.getenv("EVAL_PASS_THRESHOLD", "0.7")),
    )
