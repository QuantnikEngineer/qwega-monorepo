"""Authentication dependency helpers for protected routes."""

from fastapi import HTTPException, Request

from app.core.config import settings


def _is_trusted_proxy(request: Request) -> bool:
    """Check if the request comes from a trusted gateway.

    Trust is established by either:
    1. Source IP in TRUSTED_PROXY_IPS (works for localhost/sidecar), OR
    2. Valid X-Internal-Key header matching INTERNAL_API_KEY (works for
       Cloud Run service-to-service where IPs are dynamic).
    """
    # Header-based trust (gateway sends INTERNAL_API_KEY)
    internal_key = request.headers.get("X-Internal-Key", "")
    if internal_key and internal_key == settings.internal_api_key:
        return True

    # IP-based trust (localhost / sidecar)
    if request.client is None or not request.client.host:
        return False
    trusted_proxy_ips = {
        ip.strip()
        for ip in settings.trusted_proxy_ips.split(",")
        if ip.strip()
    }
    return request.client.host in trusted_proxy_ips


async def get_current_user(request: Request) -> dict:
    """Resolve current user from trusted gateway headers or Bearer token."""
    user_id = request.headers.get("X-User-Id")
    trusted_proxy = _is_trusted_proxy(request)
    if user_id and trusted_proxy:
        roles_header = request.headers.get("X-User-Roles", "")
        capabilities_header = request.headers.get("X-User-Capabilities", "")
        return {
            "user_id": user_id,
            "email": request.headers.get("X-User-Email", ""),
            "roles": [role.strip() for role in roles_header.split(",") if role.strip()],
            "capabilities": [cap.strip() for cap in capabilities_header.split(",") if cap.strip()],
            "org_id": request.headers.get("X-User-Org-Id", ""),
        }

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            try:
                claims = request.app.state.jwt_manager.decode_access_token(token)
                return {
                    "user_id": str(claims.get("sub", "")),
                    "email": str(claims.get("email", "")),
                    "roles": claims.get("roles", []) or [],
                    "capabilities": claims.get("capabilities", []) or [],
                    "org_id": str(claims.get("org_id", "")),
                }
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=401, detail="Invalid access token") from exc

    raise HTTPException(status_code=401, detail="Authentication required")
