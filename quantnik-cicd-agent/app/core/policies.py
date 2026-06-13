from functools import lru_cache
import json
from pathlib import Path


POLICIES_ROOT = Path(__file__).resolve().parents[1] / "policies"


@lru_cache
def load_policy(relative_path: str):
    return json.loads((POLICIES_ROOT / relative_path).read_text())