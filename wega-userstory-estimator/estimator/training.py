from __future__ import annotations

"""Reserved for future offline model training workflows.

The current local estimator trains a lightweight model at service startup using the synthetic
historical backlog. This module is intentionally present so a future enterprise implementation
can move training into a dedicated offline pipeline without restructuring the repository.
"""
