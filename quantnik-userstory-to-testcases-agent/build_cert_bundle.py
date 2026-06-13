"""
Build a combined CA certificate bundle at runtime for the
UserStory-to-TestCases agent.

Merges (in order, all optional):
  1. Python's default certifi bundle (public CAs)
  2. Repo-local ``cert/combined_ca.pem`` or ``cert/Cert.txt`` (corporate /
     self-signed CAs needed to reach internal Langfuse / OTLP endpoints)
  3. Custom CA PEM from the ``LANGFUSE_CA_CERT`` env var
     (populated from Secret Manager or equivalent)

The combined PEM is written to a process-private temp directory and its
path is returned. Callers (typically ``main.py``) point standard SSL env
vars (``SSL_CERT_FILE``, ``REQUESTS_CA_BUNDLE``, ``OTEL_CA_CERT_PATH``) at
this file BEFORE any networking library is imported.

Usage:
    import build_cert_bundle
    ca_path = build_cert_bundle.build()
    if ca_path.exists():
        os.environ.setdefault("SSL_CERT_FILE", str(ca_path))
        os.environ.setdefault("REQUESTS_CA_BUNDLE", str(ca_path))
        os.environ.setdefault("OTEL_CA_CERT_PATH", str(ca_path))
"""

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_CERT_DIR = Path(tempfile.mkdtemp(prefix="userstory-testcases-certs-"))
OUTPUT_FILE = _CERT_DIR / "combined_ca.pem"


def _get_certifi_bundle() -> str:
    try:
        import certifi
        bundle_path = certifi.where()
        logger.debug(
            "build_cert_bundle._get_certifi_bundle: using certifi bundle at %s",
            bundle_path,
        )
        return Path(bundle_path).read_text(encoding="utf-8")
    except ImportError:
        logger.debug(
            "build_cert_bundle._get_certifi_bundle: certifi not installed, skipping"
        )
        return ""


def _get_repo_cert_bundle() -> str:
    """Read the project's local cert files if present.

    Looks for ``cert/combined_ca.pem`` first (multi-cert bundle), then
    falls back to ``cert/Cert.txt`` (single corporate ALB cert).
    Without merging these into the runtime bundle, OTLP exports hit
    SSLCertVerificationError against the self-signed Langfuse ALB.
    """
    repo_root = Path(__file__).resolve().parent
    for candidate in (
        repo_root / "cert" / "combined_ca.pem",
        repo_root / "cert" / "Cert.txt",
    ):
        try:
            if candidate.is_file():
                content = candidate.read_text(encoding="utf-8")
                if "BEGIN CERTIFICATE" in content:
                    logger.debug(
                        "build_cert_bundle._get_repo_cert_bundle: using %s",
                        candidate,
                    )
                    return content
        except Exception as exc:
            logger.debug(
                "build_cert_bundle._get_repo_cert_bundle: skip %s (%s)",
                candidate,
                exc,
            )
    logger.debug(
        "build_cert_bundle._get_repo_cert_bundle: no repo cert bundle found"
    )
    return ""


def _get_corporate_cert() -> str:
    """Return the corporate cert from the ``LANGFUSE_CA_CERT`` env var.

    The value may be raw PEM text OR base64-encoded PEM (handled
    defensively so existing deployments that base64-encode the secret
    continue to work).
    """
    cert_content = os.getenv("LANGFUSE_CA_CERT", "")
    if not cert_content:
        logger.debug(
            "build_cert_bundle._get_corporate_cert: LANGFUSE_CA_CERT not set"
        )
        return ""
    if "BEGIN CERTIFICATE" in cert_content:
        logger.debug(
            "build_cert_bundle._get_corporate_cert: found raw PEM in LANGFUSE_CA_CERT"
        )
        return cert_content
    try:
        import base64

        decoded = base64.b64decode(cert_content).decode("utf-8", errors="replace")
        if "BEGIN CERTIFICATE" in decoded:
            logger.debug(
                "build_cert_bundle._get_corporate_cert: decoded base64 PEM from LANGFUSE_CA_CERT"
            )
            return decoded
    except Exception as exc:
        logger.debug(
            "build_cert_bundle._get_corporate_cert: failed to decode LANGFUSE_CA_CERT as base64 (%s)",
            exc,
        )
    logger.debug(
        "build_cert_bundle._get_corporate_cert: LANGFUSE_CA_CERT did not look like PEM or base64-PEM"
    )
    return ""


def build() -> Path:
    """Build and write the combined CA bundle. Returns the bundle path."""
    logger.debug("build_cert_bundle.build: entry")
    parts: list[str] = []
    certifi_bundle = _get_certifi_bundle()
    if certifi_bundle:
        parts.append(certifi_bundle)
    repo_bundle = _get_repo_cert_bundle()
    if repo_bundle:
        parts.append(repo_bundle)
    corporate_cert = _get_corporate_cert()
    if corporate_cert:
        parts.append(corporate_cert)
    if not parts:
        logger.warning(
            "build_cert_bundle.build: no certificates found to bundle"
        )
        logger.debug("build_cert_bundle.build: exit - no output written")
        return OUTPUT_FILE
    combined = "\n".join(parts)
    OUTPUT_FILE.write_text(combined, encoding="utf-8")
    cert_count = combined.count("-----BEGIN CERTIFICATE-----")
    logger.info(
        "build_cert_bundle.build: wrote %d certificates to %s (%.1f KB)",
        cert_count,
        OUTPUT_FILE,
        len(combined) / 1024,
    )
    logger.debug("build_cert_bundle.build: exit")
    return OUTPUT_FILE


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    build()
