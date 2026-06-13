"""
utils/docx_generator.py

Serialises BRDDocument → JSON → calls generate_brd_docx.js via
asyncio.create_subprocess_exec (non-blocking, Windows-safe).
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from models.brd_models import BRDDocument

logger = logging.getLogger(__name__)

_JS_SCRIPT = Path(__file__).parent / "generate_brd_docx.js"

# ── Section key → human title (must match JS BRD_TEMPLATE order) ─────────────
_SECTION_KEY_TO_TITLE: dict[str, str] = {
    "executive_summary":       "1. Executive Summary",
    "business_background":     "2. Business Background & Current State (As-Is)",
    "business_objectives":     "3. Business Objectives & Success Criteria",
    "scope_definition":        "4. Scope Definition",
    "in_scope":                "4.1 In Scope",
    "out_of_scope":            "4.2 Out of Scope",
    "future_state":            "5. Future State (To-Be Processes)",
    "business_requirements":   "6. Business Requirements",
    "nfr":                     "7. Non-Functional Requirements (NFRs)",
    "nfr_performance":         "7.1 Performance",
    "nfr_scalability":         "7.2 Scalability",
    "nfr_security":            "7.3 Security",
    "nfr_availability":        "7.4 Availability & Reliability",
    "nfr_usability":           "7.5 Usability",
    "nfr_data_quality":        "7.6 Data Quality & Integrity",
    "nfr_maintainability":     "7.7 Maintainability",
    "nfr_compliance":          "7.8 Compliance & Regulatory",
    "nfr_integration":         "7.9 Integration Requirements",
    "nfr_disaster_recovery":   "7.10 Disaster Recovery",
    "assumptions_constraints": "8. Assumptions & Constraints",
    "dependencies":            "9. Dependencies",
    "risks":                   "10. Risks & Mitigation Plans",
    "stakeholder_analysis":    "11. Stakeholder Analysis",
    "raci_matrix":             "12. RACI Matrix",
    "glossary":                "13. Glossary & Definitions",
    "appendices":              "14. Appendices",
}

_TITLE_TO_KEY: dict[str, str] = {
    t.lower(): k for k, t in _SECTION_KEY_TO_TITLE.items()
}

_EXTRA_ALIASES: dict[str, str] = {
    "executive summary":             "executive_summary",
    "business background":           "business_background",
    "current state":                 "business_background",
    "business objectives":           "business_objectives",
    "success criteria":              "business_objectives",
    "scope":                         "scope_definition",
    "in scope":                      "in_scope",
    "out of scope":                  "out_of_scope",
    "future state":                  "future_state",
    "to-be":                         "future_state",
    "business requirements":         "business_requirements",
    "non-functional requirements":   "nfr",
    "nfrs":                          "nfr",
    "performance":                   "nfr_performance",
    "scalability":                   "nfr_scalability",
    "security":                      "nfr_security",
    "availability":                  "nfr_availability",
    "usability":                     "nfr_usability",
    "data quality":                  "nfr_data_quality",
    "maintainability":               "nfr_maintainability",
    "compliance":                    "nfr_compliance",
    "integration requirements":      "nfr_integration",
    "disaster recovery":             "nfr_disaster_recovery",
    "assumptions":                   "assumptions_constraints",
    "constraints":                   "assumptions_constraints",
    "dependencies":                  "dependencies",
    "risks":                         "risks",
    "stakeholder analysis":          "stakeholder_analysis",
    "raci":                          "raci_matrix",
    "raci matrix":                   "raci_matrix",
    "glossary":                      "glossary",
    "definitions":                   "glossary",
    "appendices":                    "appendices",
    "appendix":                      "appendices",
}


def _title_to_key(title: str) -> str:
    clean = re.sub(r"^\d+(\.\d+)*[\.\s]+", "", title).strip().lower()
    full  = title.strip().lower()
    for lookup in (full, clean):
        if lookup in _TITLE_TO_KEY:
            return _TITLE_TO_KEY[lookup]
        if lookup in _EXTRA_ALIASES:
            return _EXTRA_ALIASES[lookup]
    for alias, key in _EXTRA_ALIASES.items():
        if alias in clean or clean in alias:
            return key
    return re.sub(r"[^a-z0-9]+", "_", clean).strip("_")


async def generate_brd_docx(brd: BRDDocument, output_dir: str) -> str:
    """
    Async, non-blocking BRD docx generation.
    Serialises BRDDocument to JSON, calls Node.js via asyncio subprocess.
    Returns absolute path to the generated .docx file.
    """
    # Build payload
    sections_dict = {
        _title_to_key(s.title): {
            "content":       s.content,
            "is_ai_assumed": s.is_ai_assumed,
        }
        for s in brd.sections
    }

    payload = {
        "project_name": brd.project_name,
        "version":      brd.version,
        "date":         datetime.now().strftime("%B %d, %Y"),
        "prepared_by":  "BRD Agent",
        "status":       "Draft",
        "stakeholders": [
            {
                "name":  s.name,
                "email": s.email,
                "role":  s.role.value if hasattr(s.role, "value") else str(s.role),
            }
            for s in brd.stakeholders
        ],
        "sections": sections_dict,
    }

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    safe  = re.sub(r"[^\w\-_\. ]", "_", brd.project_name).replace(" ", "_")
    fname = f"BRD_{safe}_v{brd.version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    out   = os.path.abspath(os.path.join(output_dir, fname))

    # Write temp JSON (use delete=False so Node can read it on Windows too)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name

        # ── Run Node.js in a thread executor ─────────────────────────────────
        # asyncio.create_subprocess_exec needs ProactorEventLoop on Windows,
        # but uvicorn uses SelectorEventLoop. run_in_executor works on both.
        import subprocess as _sp

        def _run_node():
            return _sp.run(
                ["node", str(_JS_SCRIPT), tmp_path, out],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(_JS_SCRIPT.parent),
            )

        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_node)

        if result.returncode != 0:
            err_msg = (result.stderr or "").strip()
            out_msg = (result.stdout or "").strip()
            logger.error("JS generator failed (rc=%d):\nSTDOUT: %s\nSTDERR: %s",
                         result.returncode, out_msg, err_msg)
            raise RuntimeError(
                f"BRD docx generation failed (exit {result.returncode}): "
                f"{err_msg or out_msg}"
            )

        # Verify the output file is a valid non-empty docx
        if not os.path.exists(out):
            raise RuntimeError("Node.js ran successfully but output file was not created.")
        file_size = os.path.getsize(out)
        if file_size < 1000:
            raise RuntimeError(
                f"Generated file is too small ({file_size} bytes) — likely corrupt. "
                "Check server logs for JS errors."
            )
        # Validate the docx is a structurally sound OOXML package: it must
        # be a readable ZIP and contain the [Content_Types].xml manifest
        # that every Word file ships with.
        try:
            import zipfile
            with zipfile.ZipFile(out) as zf:
                bad = zf.testzip()
                if bad is not None:
                    raise RuntimeError(f"Generated docx has corrupt entry: {bad}")
                names = set(zf.namelist())
                if "[Content_Types].xml" not in names:
                    raise RuntimeError(
                        "Generated docx is missing [Content_Types].xml — invalid OOXML package."
                    )
        except zipfile.BadZipFile as exc:
            try:
                os.unlink(out)
            except OSError:
                pass
            raise RuntimeError(f"Generated file is not a valid docx (bad ZIP): {exc}") from exc

        logger.info("BRD docx written: %s (%d bytes)", out, file_size)
        return out

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass