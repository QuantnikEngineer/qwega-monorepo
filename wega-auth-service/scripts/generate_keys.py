"""RSA Key Pair Generator for JWT Signing (Development Use)."""

import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_keypair(key_dir: str = "keys") -> None:
    """Generate 2048-bit RSA key pair for local JWT signing."""
    os.makedirs(key_dir, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(os.path.join(key_dir, "private.pem"), "wb") as file:
        file.write(private_pem)

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with open(os.path.join(key_dir, "public.pem"), "wb") as file:
        file.write(public_pem)

    print(f"RSA key pair generated in {key_dir}/")


if __name__ == "__main__":
    generate_rsa_keypair()
