"""SSRF-safe URL validation for user-configured tool endpoints.

Validates that tool URLs point to legitimate external services and blocks
requests to internal infrastructure (localhost, private networks, cloud
metadata endpoints).

Applied at:
  - Write-time: when users save tool configuration (defense-in-depth)
  - Read-time: when gateway requests secrets (belt-and-suspenders)
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Cloud metadata endpoints (AWS, GCP, Azure)
_METADATA_HOSTS = frozenset({
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.goog",
})

# Blocked schemes — only HTTPS (and HTTP for dev) are legitimate tool URLs
_ALLOWED_SCHEMES = frozenset({"http", "https"})


class UnsafeURLError(ValueError):
    """Raised when a tool URL fails SSRF validation."""


def validate_tool_url(url: str, *, allow_private: bool = False) -> str:
    """Validate a tool URL is safe to proxy to.

    Args:
        url: The user-provided tool URL to validate.
        allow_private: If True, skip private-network checks (for dev/testing).

    Returns:
        The validated URL (stripped of trailing slashes).

    Raises:
        UnsafeURLError: If the URL is unsafe to proxy to.
    """
    if not url or not url.strip():
        raise UnsafeURLError("URL is empty")

    parsed = urlparse(url.strip())

    # Scheme check
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Scheme '{parsed.scheme}' is not allowed (must be http or https)")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL has no hostname")

    # Block cloud metadata endpoints
    if hostname in _METADATA_HOSTS:
        raise UnsafeURLError(f"Blocked metadata endpoint: {hostname}")

    # Resolve hostname and check IP ranges
    if not allow_private:
        _check_resolved_ip(hostname)

    return url.strip().rstrip("/")


def _check_resolved_ip(hostname: str) -> None:
    """Resolve hostname and ensure it doesn't point to private/loopback addresses."""
    # First check if hostname is a raw IP literal
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        pass  # Not a raw IP, proceed with DNS resolution
    else:
        _reject_private_ip(addr, hostname)
        return

    try:
        # getaddrinfo returns all resolved addresses
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        # DNS resolution failed — allow it (the upstream will fail naturally)
        return

    for family, _, _, _, sockaddr in results:
        ip_str = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        _reject_private_ip(addr, hostname)


def _reject_private_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address, hostname: str) -> None:
    """Reject loopback, private, and link-local addresses."""
    if addr.is_loopback:
        raise UnsafeURLError(f"Loopback address blocked: {hostname} → {addr}")
    if addr.is_private:
        raise UnsafeURLError(f"Private network address blocked: {hostname} → {addr}")
    if addr.is_link_local:
        raise UnsafeURLError(f"Link-local address blocked: {hostname} → {addr}")
    if addr.is_reserved:
        raise UnsafeURLError(f"Reserved address blocked: {hostname} → {addr}")
