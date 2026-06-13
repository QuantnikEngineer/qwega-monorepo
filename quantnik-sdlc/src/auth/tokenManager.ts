/**
 * Token Manager
 *
 * In-memory access token storage. Access tokens are NEVER stored in
 * browser persistent storage (ADR-005). Refresh tokens live in
 * httpOnly cookies managed by the Auth Service.
 */

let accessToken: string | null = null;
let tokenExpiresAt = 0;

export function getAccessToken(): string | null {
  if (accessToken && Date.now() >= tokenExpiresAt - 30_000) {
    return null;
  }
  return accessToken;
}

export function setAccessToken(token: string, expiresInSeconds: number): void {
  accessToken = token;
  tokenExpiresAt = Date.now() + expiresInSeconds * 1000;
}

export function clearTokens(): void {
  accessToken = null;
  tokenExpiresAt = 0;
}

export function isTokenExpiringSoon(): boolean {
  return accessToken !== null && Date.now() >= tokenExpiresAt - 60_000;
}

export function getTokenExpiresAt(): number {
  return tokenExpiresAt;
}
