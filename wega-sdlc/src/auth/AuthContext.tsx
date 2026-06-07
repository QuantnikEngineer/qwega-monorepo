import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { AuthContextType, AuthUser, LoginResult } from './types';
import { AbilityContext, defineAbilitiesFor } from './abilities';
import { changePassword as authChangePassword, getProfile, login as authLogin, logout as authLogout } from '../services/authApi';
import { coordinatedRefresh } from './refreshCoordinator';
import {
  broadcastLogout,
  broadcastRefreshComplete,
  broadcastRefreshStarted,
  broadcastTokenRefreshed,
  closeBroadcastSync,
  initBroadcastSync,
  isRefreshInProgress,
} from './broadcastSync';
import { clearTokens, getAccessToken as getStoredAccessToken, setAccessToken } from './tokenManager';
import { queryClient } from '../providers/QueryProvider';

const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED === 'true';
const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  const waitForPeerRefresh = useCallback(async (): Promise<string | null> => {
    const timeoutMs = 8_000;
    const startedAt = Date.now();

    while (isRefreshInProgress() && Date.now() - startedAt < timeoutMs) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    return getStoredAccessToken();
  }, []);

  const refreshWithLock = useCallback(async () => {
    if (isRefreshInProgress()) {
      const sharedToken = await waitForPeerRefresh();
      if (sharedToken) {
        return null;
      }
    }

    broadcastRefreshStarted();
    try {
      const refreshed = await coordinatedRefresh();
      broadcastTokenRefreshed(refreshed.accessToken, refreshed.expiresIn);
      if (refreshed.user) {
        setUser(refreshed.user);
      }
      return refreshed;
    } finally {
      broadcastRefreshComplete();
    }
  }, [waitForPeerRefresh]);

  const scheduleTokenRefresh = useCallback(
    (expiresInMs: number) => {
      clearRefreshTimer();
      const refreshIn = Math.max(expiresInMs - 60_000, 0);
      refreshTimerRef.current = setTimeout(async () => {
        const maxRetries = 2;
        for (let attempt = 0; attempt <= maxRetries; attempt++) {
          try {
            const refreshed = await refreshWithLock();
            if (refreshed) {
              scheduleTokenRefresh(refreshed.expiresIn * 1000);
            }
            return;
          } catch (err) {
            const isTransient =
              err instanceof TypeError || // network error
              (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status >= 500);
            if (!isTransient || attempt === maxRetries) {
              clearTokens();
              setUser(null);
              return;
            }
            // Wait before retry (1s, then 3s)
            await new Promise((r) => setTimeout(r, (attempt + 1) * 2000));
          }
        }
      }, refreshIn);
    },
    [clearRefreshTimer, refreshWithLock]
  );

  const login = useCallback(
    async (email: string, password: string): Promise<LoginResult> => {
      const result = await authLogin(email, password);
      setAccessToken(result.accessToken, result.expiresIn);
      setUser(result.user);
      scheduleTokenRefresh(result.expiresIn * 1000);
      broadcastTokenRefreshed(result.accessToken, result.expiresIn);

      // Fetch complete profile in the background — the login response may
      // lack project assignments, full capabilities, or allowed agents.
      // The /auth/me endpoint returns the canonical complete user profile.
      const loginToken = result.accessToken;
      getProfile(loginToken)
        .then((fullProfile) => {
          // Only apply if the user is still on the same session (not logged
          // out or logged in as a different user since this request started).
          if (getStoredAccessToken() !== null) {
            setUser(fullProfile);
          }
        })
        .catch(() => {
          // Keep the login-response user if profile fetch fails
        });

      return result;
    },
    [scheduleTokenRefresh]
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await authLogout();
    } finally {
      clearTokens();
      clearRefreshTimer();
      queryClient.clear();
      setUser(null);
      broadcastLogout();
    }
  }, [clearRefreshTimer]);

  const getAccessToken = useCallback((): string | null => {
    return getStoredAccessToken();
  }, []);

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string): Promise<void> => {
      await authChangePassword(currentPassword, newPassword);
      setUser((prev) => (prev ? { ...prev, mustChangePassword: false } : prev));
    },
    []
  );

  useEffect(() => {
    initBroadcastSync({
      onTokenRefreshed: (token, expiresIn) => {
        setAccessToken(token, expiresIn);
        scheduleTokenRefresh(expiresIn * 1000);
      },
      onLogout: () => {
        clearTokens();
        clearRefreshTimer();
        setUser(null);
      },
    });

    if (!AUTH_ENABLED) {
      setIsLoading(false);
      return () => {
        closeBroadcastSync();
        clearRefreshTimer();
      };
    }

    let cancelled = false;

    async function tryRestoreSession() {
      try {
        const refreshed = await refreshWithLock();
        if (cancelled) return;
        if (refreshed) {
          scheduleTokenRefresh(refreshed.expiresIn * 1000);
        }
        const tokenForProfile = refreshed?.accessToken ?? getStoredAccessToken();
        if (!tokenForProfile) {
          throw new Error('No access token available after session restore');
        }
        const profile = await getProfile(tokenForProfile);
        if (!cancelled) {
          setUser(profile);
        }
      } catch {
        if (!cancelled) {
          clearTokens();
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void tryRestoreSession();

    return () => {
      cancelled = true;
      closeBroadcastSync();
      clearRefreshTimer();
    };
  }, [clearRefreshTimer, refreshWithLock, scheduleTokenRefresh]);

  const isAuthenticated = user !== null;
  const ability = useMemo(() => defineAbilitiesFor(user?.capabilities ?? []), [user?.capabilities]);

  const value: AuthContextType = {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    changePassword,
    getAccessToken,
  };

  return (
    <AuthContext.Provider value={value}>
      <AbilityContext.Provider value={ability}>
        {children}
      </AbilityContext.Provider>
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
