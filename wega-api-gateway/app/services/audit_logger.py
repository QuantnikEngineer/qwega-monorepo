"""Structured audit logging helpers."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("wega.gateway.audit")


class AuditLogger:
    """Emit deterministic, token-safe audit records."""

    def __init__(self, sink: Any | None = None) -> None:
        self._sink = sink or logger.info

    def emit_authenticated_request(
        self,
        *,
        user_id: str,
        action: str,
        method: str,
        status: int,
        request_id: str,
        source_ip: str,
    ) -> dict[str, Any]:
        """Write one structured authenticated-request audit entry."""
        event = {
            "user_id": user_id,
            "action": action,
            "method": method,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "source_ip": source_ip,
        }
        self._sink(json.dumps(event, sort_keys=True))
        return event
