#!/bin/sh
# =============================================================================
# Container entrypoint
# 1. Auto-generate JWT keys if not present (dev mode)
# 2. Run Alembic migrations (idempotent — safe on every startup)
# 3. Start the application
# =============================================================================
set -e

# ---- Step 1: JWT Key Generation ----
KEY_DIR="${JWT_KEY_DIR:-/app/keys}"
PRIVATE_KEY="${JWT_PRIVATE_KEY_PATH:-$KEY_DIR/private.pem}"
PUBLIC_KEY="${JWT_PUBLIC_KEY_PATH:-$KEY_DIR/public.pem}"

if [ ! -f "$PRIVATE_KEY" ] || [ ! -f "$PUBLIC_KEY" ]; then
    echo "[entrypoint] JWT keys not found — generating RSA-2048 pair..."
    mkdir -p "$(dirname "$PRIVATE_KEY")"
    python - <<'KEYGEN'
import os, sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
priv_path = os.environ.get("JWT_PRIVATE_KEY_PATH", "/app/keys/private.pem")
pub_path = os.environ.get("JWT_PUBLIC_KEY_PATH", "/app/keys/public.pem")
os.makedirs(os.path.dirname(priv_path), exist_ok=True)

with open(priv_path, "wb") as f:
    f.write(private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
with open(pub_path, "wb") as f:
    f.write(private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo))
print(f"[entrypoint] Keys written to {priv_path} and {pub_path}")
KEYGEN
else
    echo "[entrypoint] JWT keys found — skipping generation."
fi

# ---- Step 2: Database Migrations ----
# On Cloud Run services, migrations are handled by a separate Cloud Run Job
# (executed by deploy.sh before the service deploys). Skip here to avoid
# startup latency and multi-instance race conditions.
# For local dev (docker run / docker-compose), migrations still run automatically.
if [ -z "${SKIP_MIGRATIONS:-}" ] && [ -n "${K_SERVICE:-}" ]; then
    SKIP_MIGRATIONS="true"
fi

if [ "${SKIP_MIGRATIONS:-false}" = "true" ]; then
    echo "[entrypoint] Skipping Alembic migrations (handled by Cloud Run Job or SKIP_MIGRATIONS=true)."
else
    echo "[entrypoint] Running database migrations (local/dev mode)..."
    python -m alembic upgrade head
    echo "[entrypoint] Migrations complete."
fi

# ---- Step 3: Start Application ----
exec "$@"
