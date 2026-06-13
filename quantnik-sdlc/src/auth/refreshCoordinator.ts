/**
 * Refresh Coordinator
 *
 * Deduplicates concurrent token refresh requests within a single tab.
 * Both apiClient (401 handler) and AuthContext (scheduled timer) call
 * this module instead of raw refreshToken(), ensuring at most ONE HTTP
 * refresh request is in-flight at any time.
 *
 * Cross-tab coordination continues to be handled by broadcastSync.ts
 * in AuthContext (BroadcastChannel REFRESH_STARTED / REFRESH_COMPLETE).
 */

import { refreshToken } from '../services/authApi';
import { setAccessToken, getAccessToken } from './tokenManager';
import type { TokenRefreshResult } from './types';

export interface CoordinatedRefreshResult extends TokenRefreshResult {
  user?: any;
}

let inflight: Promise<CoordinatedRefreshResult> | null = null;

/**
 * Execute a token refresh with single-flight deduplication.
 *
 * If a refresh is already in-flight (from apiClient 401 handler OR
 * AuthContext scheduled timer), callers receive the same promise
 * instead of firing a duplicate HTTP request.
 *
 * On success the new access token is written to tokenManager.
 */
export function coordinatedRefresh(): Promise<CoordinatedRefreshResult> {
  if (inflight) return inflight;

  inflight = refreshToken()
    .then((result) => {
      setAccessToken(result.accessToken, result.expiresIn);
      return result;
    })
    .finally(() => {
      inflight = null;
    });

  return inflight;
}

/**
 * Whether a refresh attempt should be considered a definitive auth
 * failure (vs. a transient network error that can be retried).
 * Used by apiClient to decide whether to wipe local auth state.
 */
export function isDefinitiveAuthFailure(err: unknown): boolean {
  if (err && typeof err === 'object' && 'status' in err) {
    const status = (err as { status: number }).status;
    // 401/403 from the refresh endpoint = cookie is invalid / revoked
    return status === 401 || status === 403;
  }
  return false;
}

/**
 * Check whether a newer token has been set since a given reference token.
 * Used to avoid clearing tokens when a concurrent refresh already succeeded.
 */
export function hasNewerToken(referenceToken: string | null): boolean {
  const current = getAccessToken();
  return current !== null && current !== referenceToken;
}
