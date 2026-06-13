"""Generic LLM-as-judge evaluator — agent-agnostic."""

from __future__ import annotations

import base64
import json
import logging
import os
import ssl
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from google import genai

from quantnik_evals.agent_profile import AgentProfile
from quantnik_evals.config import EvalConfig
from quantnik_evals.models import DimensionScore, EvalResult

logger = logging.getLogger(__name__)


def _ensure_ca_bundle() -> None:
    """Build a combined CA bundle from the OS cert store + certifi + Langfuse server cert.

    Sets SSL_CERT_FILE and REQUESTS_CA_BUNDLE so that httpx / urllib3
    trust corporate proxy certs (e.g. Zscaler) and self-signed server certs.
    Only runs once; skips if SSL_CERT_FILE is already set by the user.
    """
    if os.environ.get("_QUANTNIK_EVALS_CA_DONE"):
        return
    if os.environ.get("SSL_CERT_FILE"):
        os.environ["_QUANTNIK_EVALS_CA_DONE"] = "1"
        return

    try:
        import certifi
        ctx = ssl.create_default_context()
        der_certs = ctx.get_ca_certs(binary_form=True)

        td = tempfile.mkdtemp(prefix="quantnik_evals_certs_")
        bundle = os.path.join(td, "ca-bundle.pem")
        with open(bundle, "w") as f:
            f.write(open(certifi.where()).read())
            for der in der_certs:
                _write_pem(f, der)

        # Also grab self-signed cert from the Langfuse host (if any)
        _append_server_cert(bundle, os.environ.get("LANGFUSE_HOST", ""))

        os.environ["SSL_CERT_FILE"] = bundle
        os.environ["REQUESTS_CA_BUNDLE"] = bundle
        logger.debug("CA bundle built at %s (%d OS certs)", bundle, len(der_certs))
    except Exception as exc:
        logger.warning("Could not build CA bundle: %s", exc)
    os.environ["_QUANTNIK_EVALS_CA_DONE"] = "1"


def _write_pem(f, der_bytes: bytes) -> None:
    pem = base64.b64encode(der_bytes).decode()
    f.write("\n-----BEGIN CERTIFICATE-----\n")
    for i in range(0, len(pem), 64):
        f.write(pem[i : i + 64] + "\n")
    f.write("-----END CERTIFICATE-----\n")


def _append_server_cert(bundle_path: str, host_url: str) -> None:
    """Fetch a server's TLS certificate and append it to the bundle."""
    if not host_url:
        return
    import socket
    hostname = host_url.replace("https://", "").replace("http://", "").split("/")[0]
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((hostname, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                der = ssock.getpeercert(binary_form=True)
        with open(bundle_path, "a") as f:
            f.write(f"\n# Server cert for {hostname}\n")
            _write_pem(f, der)
        logger.debug("Appended server cert from %s", hostname)
    except Exception as exc:
        logger.debug("Could not fetch server cert from %s: %s", hostname, exc)


def build_langfuse_httpx_client() -> "httpx.Client":
    """Build an httpx.Client that trusts the combined CA bundle."""
    import httpx
    bundle = os.environ.get("SSL_CERT_FILE", "")
    if bundle and os.path.exists(bundle):
        return httpx.Client(verify=bundle)
    return httpx.Client()


class LLMJudge:
    """Evaluate agent outputs using an LLM as judge.

    Prompt templates are loaded from the agent profile, so the judge
    is fully agent-agnostic.
    """

    def __init__(self, config: EvalConfig, profile: AgentProfile) -> None:
        self._config = config
        self._profile = profile
        _ensure_ca_bundle()
        if config.judge_use_vertex:
            self._client = genai.Client(
                vertexai=True,
                project=config.vertex_project,
                location=config.vertex_location,
            )
        else:
            self._client = genai.Client(api_key=config.judge_api_key)

    def evaluate(
        self,
        *,
        trace_id: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        dimensions: list[str] | None = None,
    ) -> EvalResult:
        """Run LLM-as-judge evaluations on a single agent output."""
        dims = dimensions or self._profile.dimensions
        result = EvalResult(trace_id=trace_id, agent=self._profile.name)

        # Build template variables
        input_text = self._profile.extract_primary_input_text(input_data)
        output_text = self._profile.extract_primary_output_text(output_data)
        extra_vars = self._profile.format_judge_context(input_data, output_data)

        template_vars = {
            "input_text": self._truncate(input_text, 60_000),
            "output_text": self._truncate(output_text, 60_000),
            **extra_vars,
        }

        # Evaluate dimensions in parallel
        eval_dims = [(dim, self._profile.judge_prompts[dim])
                     for dim in dims if dim in self._profile.judge_prompts]
        skipped = [dim for dim in dims if dim not in self._profile.judge_prompts]
        for dim in skipped:
            logger.debug("No judge prompt for dimension '%s' — skipping", dim)

        max_workers = min(self._config.max_dim_workers, len(eval_dims)) if eval_dims else 1
        scores_map: dict[str, DimensionScore] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self._evaluate_dimension, dim, tmpl, template_vars): dim
                for dim, tmpl in eval_dims
            }
            for future in as_completed(futures):
                dim = futures[future]
                try:
                    scores_map[dim] = future.result()
                except Exception as exc:
                    logger.error("Judge evaluation failed for '%s': %s", dim, exc)
                    scores_map[dim] = DimensionScore(
                        dimension=dim,
                        score=0.0,
                        reasoning=f"Evaluation error: {type(exc).__name__}: {exc}",
                        evaluator="llm_judge",
                    )

        # Preserve original dimension order
        for dim, _ in eval_dims:
            if dim in scores_map:
                result.scores.append(scores_map[dim])

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evaluate_dimension(
        self,
        dimension: str,
        prompt_template: str,
        template_vars: dict[str, str],
    ) -> DimensionScore:
        """Evaluate a single dimension using the LLM judge."""
        # Format prompt — use safe substitution to avoid KeyError on unused vars
        prompt = self._safe_format(prompt_template, template_vars)

        response = self._client.models.generate_content(
            model=self._config.judge_model,
            contents=prompt,
            config={
                "temperature": self._config.judge_temperature,
                "response_mime_type": "application/json",
            },
        )

        raw = response.text or "{}"
        parsed = self._parse_json(raw)
        score_value = self._extract_score(parsed)

        return DimensionScore(
            dimension=dimension,
            score=score_value,
            reasoning=parsed.get("reasoning", ""),
            details=parsed,
            evaluator="llm_judge",
        )

    def _extract_score(self, parsed: dict[str, Any]) -> float:
        """Extract numeric score from parsed judge response.

        Looks for common score field names and clamps to [0, 1].
        """
        for key in ("score", "overall_score", "accuracy_score",
                     "calibration_score", "quality_score", "completeness_score",
                     "relevance_score"):
            if key in parsed:
                try:
                    return max(0.0, min(1.0, float(parsed[key])))
                except (ValueError, TypeError):
                    continue

        # Inverted metrics (lower = better)
        for key in ("false_positive_rate", "error_rate"):
            if key in parsed:
                try:
                    return max(0.0, min(1.0, 1.0 - float(parsed[key])))
                except (ValueError, TypeError):
                    continue

        return 0.0

    def _parse_json(self, text: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown fences."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            end = -1 if lines[-1].strip() == "```" else len(lines)
            cleaned = "\n".join(lines[1:end])
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse judge response as JSON: %.200s", text)
            return {"reasoning": text, "score": 0.0}

    def _safe_format(self, template: str, variables: dict[str, str]) -> str:
        """Format a template string, ignoring missing keys."""
        try:
            return template.format(**variables)
        except KeyError as e:
            logger.warning("Missing template variable %s — using partial format", e)
            # Fall back to partial formatting
            result = template
            for key, value in variables.items():
                result = result.replace("{" + key + "}", str(value))
            return result

    def _truncate(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "\n\n... [truncated]"
