/**
 * BroadcastChannel Multi-Tab Sync
 *
 * Coordinates token refresh and logout across browser tabs to prevent
 * race conditions with family-based refresh token rotation (AUTH-10).
 *
 * If BroadcastChannel is unavailable, this module no-ops.
 */

const CHANNEL_NAME = 'quantnik-auth-sync';

type AuthMessage =
  | { type: 'TOKEN_REFRESHED'; accessToken: string; expiresIn: number }
  | { type: 'LOGOUT' }
  | { type: 'REFRESH_STARTED' }
  | { type: 'REFRESH_COMPLETE' };

let channel: BroadcastChannel | null = null;
let refreshInProgress = false;

export function isRefreshInProgress(): boolean {
  return refreshInProgress;
}

export function initBroadcastSync(handlers: {
  onTokenRefreshed: (token: string, expiresIn: number) => void;
  onLogout: () => void;
}): void {
  if (typeof BroadcastChannel === 'undefined') return;

  channel = new BroadcastChannel(CHANNEL_NAME);
  channel.onmessage = (event: MessageEvent<AuthMessage>) => {
    switch (event.data.type) {
      case 'TOKEN_REFRESHED':
        handlers.onTokenRefreshed(event.data.accessToken, event.data.expiresIn);
        refreshInProgress = false;
        break;
      case 'LOGOUT':
        handlers.onLogout();
        break;
      case 'REFRESH_STARTED':
        refreshInProgress = true;
        break;
      case 'REFRESH_COMPLETE':
        refreshInProgress = false;
        break;
      default:
        break;
    }
  };
}

export function broadcastRefreshStarted(): void {
  refreshInProgress = true;
  channel?.postMessage({ type: 'REFRESH_STARTED' });
}

export function broadcastRefreshComplete(): void {
  refreshInProgress = false;
  channel?.postMessage({ type: 'REFRESH_COMPLETE' });
}

export function broadcastTokenRefreshed(accessToken: string, expiresIn: number): void {
  refreshInProgress = false;
  channel?.postMessage({ type: 'TOKEN_REFRESHED', accessToken, expiresIn });
}

export function broadcastLogout(): void {
  channel?.postMessage({ type: 'LOGOUT' });
}

export function closeBroadcastSync(): void {
  channel?.close();
  channel = null;
  refreshInProgress = false;
}
