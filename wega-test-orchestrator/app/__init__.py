"""Wega Test Orchestrator - Test Agent Orchestration Service"""

import warnings

# Suppress Pydantic V1 compatibility warning from langchain-core on Python 3.14+
warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater",
    category=UserWarning,
    module="langchain_core._api.deprecation"
)
