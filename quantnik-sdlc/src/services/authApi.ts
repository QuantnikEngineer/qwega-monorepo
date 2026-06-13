/**
 * Auth Service API
 *
 * Calls to the QUANTNIK Auth Service for login, logout, token refresh,
 * and password management.
 *
 * Routes through Vite proxy (dev) / nginx (prod) at /api/auth/*.
 * All cookie-bearing requests include credentials for httpOnly refresh cookie transport.
 */

import type { AuthUser, LoginResult, TokenRefreshResult } from '../auth/types';
import { getAccessToken } from '../auth/tokenManager';

interface ApiErrorDetail {
  message?: string;
  error?: string;
}

interface ApiError {
  detail?: string | ApiErrorDetail;
}

/** Extract a human-readable message from an API error detail. */
function extractErrorMessage(detail: string | ApiErrorDetail | undefined, fallback: string): string {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  return detail.message || detail.error || fallback;
}

function mapUser(user: any, mustChangePassword = false): AuthUser {
  return {
    id: user.id,
    email: user.email,
    displayName: user.displayName || user.display_name || '',
    roles: user.roles || [],
    capabilities: user.capabilities || [],
    allowedAgents: user.allowed_agents ?? user.allowedAgents ?? [],
    orgId: user.orgId || user.org_id || '',
    projectId: user.project_id ?? user.projectId ?? user.projects?.[0]?.id ?? undefined,
    projects: user.projects ?? [],
    mustChangePassword,
    platformCapabilities: user.platform_capabilities ?? user.platformCapabilities ?? [],
    orgCapabilities: user.org_capabilities ?? user.orgCapabilities ?? [],
    projectRoles: user.project_roles ?? user.projectRoles ?? {},
    selfCapabilities: user.self_capabilities ?? user.selfCapabilities ?? [],
  };
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const error = (await res.json().catch(() => ({ detail: 'Login failed' }))) as ApiError;
    throw new Error(extractErrorMessage(error.detail, 'Invalid email or password. Please try again.'));
  }

  const data = await res.json();
  const mustChangePassword = data.user?.must_change_password ?? data.must_change_password ?? false;

  return {
    accessToken: data.access_token,
    expiresIn: data.expires_in,
    user: mapUser(data.user || {}, mustChangePassword),
    mustChangePassword,
  };
}

export async function refreshToken(): Promise<TokenRefreshResult & { user?: AuthUser }> {
  const res = await fetch('/auth/refresh', {
    method: 'POST',
    credentials: 'include',
  });

  if (!res.ok) {
    throw new Error('Token refresh failed');
  }

  const data = await res.json();
  return {
    accessToken: data.access_token,
    expiresIn: data.expires_in,
    ...(data.user ? { user: mapUser(data.user) } : {}),
  };
}

export async function logout(): Promise<void> {
  const token = getAccessToken();

  await fetch('/auth/logout', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: 'include',
  }).catch(() => {
    // Ignore network errors on logout; client cleanup still proceeds.
  });
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const token = getAccessToken();
  const res = await fetch('/auth/change-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: 'include',
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

  if (!res.ok) {
    const error = (await res.json().catch(() => ({ detail: 'Password change failed' }))) as ApiError;
    throw new Error(extractErrorMessage(error.detail, 'Password change failed'));
  }
}

export async function register(email: string, displayName: string, password: string, projectSlug?: string): Promise<void> {
  const body: Record<string, string> = { email, display_name: displayName, password };
  if (projectSlug) body.project_slug = projectSlug;

  const res = await fetch('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const error = (await res.json().catch(() => ({ detail: 'Registration failed' }))) as ApiError;
    const detail = extractErrorMessage(error.detail, '');

    // Map HTTP status codes to user-friendly messages
    if (res.status === 409 || /already\s*(exists|registered|in\s*use)/i.test(detail)) {
      throw new Error('An account with this email already exists. Please sign in instead.');
    }
    if (res.status === 429) {
      throw new Error('Too many registration attempts. Please wait a few minutes and try again.');
    }
    if (res.status === 422) {
      throw new Error(detail || 'Please check your input and try again.');
    }

    throw new Error(detail || 'Registration failed. Please try again.');
  }
}

export interface RegistrationDefaults {
  mode: 'project' | 'pm';
  project_slug?: string;
  project_name?: string;
  role?: string;
}

export async function fetchRegistrationDefaults(): Promise<RegistrationDefaults> {
  try {
    const res = await fetch('/auth/registration-defaults');
    if (!res.ok) return { mode: 'pm' };
    return await res.json();
  } catch {
    // Network error — fall back to PM mode
    return { mode: 'pm' };
  }
}

export async function getProfile(accessToken: string): Promise<AuthUser> {
  const res = await fetch('/auth/me', {
    method: 'GET',
    headers: { Authorization: `Bearer ${accessToken}` },
    credentials: 'include',
  });

  if (!res.ok) {
    throw new Error('Failed to load user profile');
  }

  const data = await res.json();
  return mapUser(data, data.must_change_password || false);
}
