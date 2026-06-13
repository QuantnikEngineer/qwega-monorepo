/**
 * Authenticated API Client
 *
 * Wraps fetch() to inject Bearer token from tokenManager.
 * Handles 401 responses by attempting a single silent token refresh.
 */

import { clearTokens, getAccessToken } from '../auth/tokenManager';
import { coordinatedRefresh, hasNewerToken } from '../auth/refreshCoordinator';

let refreshPromise: Promise<void> | null = null;
const GATEWAY_BASE_URL = (
  typeof import.meta !== 'undefined' && import.meta.env
    ? (import.meta.env.VITE_GATEWAY_URL ?? '')
    : ''
).replace(/\/$/, '');
const ABSOLUTE_URL_PATTERN = /^https?:\/\//i;

function resolveGatewayUrl(url: string): string {
  const trimmed = url.trim();
  if (!trimmed) {
    return trimmed;
  }

  if (ABSOLUTE_URL_PATTERN.test(trimmed)) {
    if (GATEWAY_BASE_URL && !trimmed.startsWith(GATEWAY_BASE_URL)) {
      throw new Error('Direct backend URLs are not allowed. Use gateway routes.');
    }
    return trimmed;
  }

  let normalized = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  // Gateway routes that should NOT be auto-prefixed with /api.
  // Tool routes use /{toolId}/ or /{toolId}-api/ convention — matched by pattern.
  const isGatewayRoute = /^\/(api|auth|health)\b/.test(normalized)
    || /^\/(jira|confluence|github|qtest|sonarqube|sharepoint|harness-pipelines|harness-repo|snyk|trivy)(-api)?\b/.test(normalized);
  if (!isGatewayRoute) {
    normalized = `/api${normalized}`;
  }

  return GATEWAY_BASE_URL ? `${GATEWAY_BASE_URL}${normalized}` : normalized;
}

async function tryRefresh(): Promise<boolean> {
  const tokenBefore = getAccessToken();
  try {
    await coordinatedRefresh();
    return true;
  } catch {
    // Only clear tokens if the failure is definitive AND no concurrent
    // refresh succeeded (e.g., AuthContext timer already refreshed).
    if (!hasNewerToken(tokenBefore)) {
      clearTokens();
    }
    return false;
  }
}

export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const requestUrl = resolveGatewayUrl(url);
  const token = getAccessToken();
  const headers = new Headers(options.headers);

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  let res = await fetch(requestUrl, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (res.status === 401) {
    if (!refreshPromise) {
      refreshPromise = tryRefresh().then((success) => {
        refreshPromise = null;
        if (!success) throw new Error('Refresh failed');
      });
    }

    try {
      await refreshPromise;
    } catch {
      return res;
    }

    const newToken = getAccessToken();
    if (newToken) {
      headers.set('Authorization', `Bearer ${newToken}`);
      res = await fetch(requestUrl, {
        ...options,
        headers,
        credentials: 'include',
      });
    }
  }

  // 403 Forbidden — toast notification per D-38 (no retry, no throw)
  if (res.status === 403) {
    const { toast } = await import('sonner');
    toast.error('You do not have permission to perform this action');
  }

  return res;
}
