"""
Build a combined CA certificate bundle for SSL connections.

Combines three sources:
  1. certifi default bundle (standard Mozilla/Google root CAs)
  2. Windows Root CAs (from Cert:\\LocalMachine\\Root)
  3. Langfuse ALB certificate (self-signed, from LANGFUSE_CA_CERT_PATH env var)

Output: combined_ca.pem in the project root.

Usage:
    python build_cert_bundle.py
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_FILE = PROJECT_ROOT / "combined_ca.pem"


def _get_certifi_bundle() -> str:
    """Read the default certifi CA bundle."""
    try:
        import certifi
        bundle_path = certifi.where()
        print(f"  certifi bundle: {bundle_path}")
        return Path(bundle_path).read_text(encoding="utf-8")
    except ImportError:
        print("  WARNING: certifi not installed, skipping default CAs")
        return ""


def _get_windows_root_cas() -> str:
    """Export all Windows Root CAs via PowerShell."""
    print("  Exporting Windows Root CAs via PowerShell...")
    ps_script = (
        "Get-ChildItem Cert:\\LocalMachine\\Root | ForEach-Object { "
        "$b64 = [Convert]::ToBase64String($_.RawData, 'InsertLineBreaks'); "
        "\"-----BEGIN CERTIFICATE-----`n$b64`n-----END CERTIFICATE-----\" }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"  WARNING: PowerShell export failed: {result.stderr.strip()}")
            return ""
        certs = result.stdout.strip()
        count = certs.count("-----BEGIN CERTIFICATE-----")
        print(f"  Exported {count} Windows Root CAs")
        return certs
    except Exception as e:
        print(f"  WARNING: Could not export Windows CAs: {e}")
        return ""


def _get_langfuse_alb_cert() -> str:
    """Read the Langfuse ALB certificate from the path in LANGFUSE_CA_CERT_PATH."""
    cert_path = os.getenv("LANGFUSE_CA_CERT_PATH", "")
    if not cert_path:
        print("  LANGFUSE_CA_CERT_PATH not set, skipping ALB cert")
        return ""
    p = Path(cert_path)
    if not p.exists():
        print(f"  WARNING: Langfuse cert not found at {p}")
        return ""
    content = p.read_text(encoding="utf-8").strip()
    if "-----BEGIN CERTIFICATE-----" not in content:
        print("  WARNING: Langfuse cert file does not contain PEM data")
        return ""
    count = content.count("-----BEGIN CERTIFICATE-----")
    print(f"  Langfuse ALB cert: {p} ({count} cert(s))")
    return content


def build():
    """Build combined_ca.pem from all three sources."""
    print("Building combined CA bundle...")

    parts = []

    # 1. certifi defaults
    certifi_certs = _get_certifi_bundle()
    if certifi_certs:
        parts.append(f"# === certifi default CAs ===\n{certifi_certs}")

    # 2. Windows Root CAs
    win_certs = _get_windows_root_cas()
    if win_certs:
        parts.append(f"\n# === Windows Root CAs ===\n{win_certs}")

    # 3. Langfuse ALB cert
    alb_cert = _get_langfuse_alb_cert()
    if alb_cert:
        parts.append(f"\n# === Langfuse ALB Certificate ===\n{alb_cert}")

    if not parts:
        print("ERROR: No certificates collected. Cannot build bundle.")
        sys.exit(1)

    combined = "\n".join(parts) + "\n"
    OUTPUT_FILE.write_text(combined, encoding="utf-8")

    size_kb = OUTPUT_FILE.stat().st_size / 1024
    total_certs = combined.count("-----BEGIN CERTIFICATE-----")
    print(f"\n✅ Combined CA bundle written to: {OUTPUT_FILE}")
    print(f"   Size: {size_kb:.1f} KB, Certificates: {total_certs}")
    return OUTPUT_FILE


if __name__ == "__main__":
    build()
