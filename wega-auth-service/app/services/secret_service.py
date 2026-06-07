"""
Secret Service
==============
Fernet-based symmetric encryption for project secrets (PAT tokens, API keys).
Local dev uses a file-based key; production uses GCP Secret Manager.
"""

import base64

from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-initialize Fernet cipher from settings.wega_secret_key or generate one."""
    global _fernet
    if _fernet is not None:
        return _fernet

    key = settings.wega_secret_key
    if not key:
        key = Fernet.generate_key().decode()
        logger.warning(
            "[secrets] WEGA_SECRET_KEY not set — generated ephemeral key. "
            "Set WEGA_SECRET_KEY in .env for persistent encryption."
        )
    else:
        try:
            Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            raise ValueError("WEGA_SECRET_KEY is not a valid Fernet key")

    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret value. Returns base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a secret value."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    """Generate a new Fernet key (for bootstrapping .env)."""
    return Fernet.generate_key().decode()
