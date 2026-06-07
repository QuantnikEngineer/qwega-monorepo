"""Helpers for loading test configuration from data/config.json with env-var overrides."""
import json
import os
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config.json"


def load_config() -> dict:
    """Load configuration from data/config.json.

    Environment variables of the same name override the JSON values, so CI can
    keep the file as a checked-in default while overriding secrets at runtime.
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    base_url = os.environ.get("BASE_URL", cfg.get("BASE_URL", ""))
    cfg["BASE_URL"] = base_url.rstrip("/") if base_url else ""

    headless_env = os.environ.get("HEADLESS")
    if headless_env is not None:
        cfg["HEADLESS"] = headless_env.lower() == "true"
    else:
        cfg["HEADLESS"] = bool(cfg.get("HEADLESS", False))

    cfg["TEST_EMAIL"] = os.environ.get("TEST_EMAIL", cfg.get("TEST_EMAIL", ""))
    cfg["TEST_PASSWORD"] = os.environ.get("TEST_PASSWORD", cfg.get("TEST_PASSWORD", ""))

    return cfg
