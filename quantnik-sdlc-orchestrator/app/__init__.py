"""Quantnik SDLC Orchestrator - Parent orchestrator for planning and test workflows"""

import warnings

# Suppress langchain-core Pydantic V1 compatibility warning for Python 3.14+
# This is an upstream issue in langchain-core that hasn't been fixed yet
warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater",
    category=UserWarning,
    module="langchain_core._api.deprecation"
)
