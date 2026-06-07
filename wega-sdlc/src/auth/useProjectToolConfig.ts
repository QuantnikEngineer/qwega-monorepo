/**
 * useProjectToolConfig — fetches project tool settings from the backend.
 *
 * Returns a map of toolId → { ready, config } driven by the backend-computed
 * `ready` flag. Components use `ready` to decide whether to show/hide
 * integration sections (sidebar panels, etc.).
 *
 * Re-fetches when the user's projectId changes. Gracefully returns empty
 * when no project is active.
 */

import { useCallback, useEffect, useState } from 'react';
import { useAuth } from './AuthContext';
import { apiFetch } from '../services/apiClient';

export interface ToolConfig {
  toolId: string;
  ready: boolean;
  config: {
    url?: string;
    projectKey?: string;
    spaceKey?: string;
    spaceId?: string;
    email?: string;
    [key: string]: string | undefined;
  };
  secretKeys: string[];
  hasSecrets: boolean;
}

interface ToolSettingsResponse {
  projectId: string;
  tools: Array<{
    toolId: string;
    ready: boolean;
    platformEnabled: boolean;
    projectEnabled: boolean;
    configured: boolean;
    config: Record<string, any>;
    [key: string]: any;
  }>;
}

export function useProjectToolConfig(overrideProjectId?: string | null): {
  tools: Record<string, ToolConfig>;
  isLoading: boolean;
  error: string | null;
  refetch: () => void;
} {
  const { user } = useAuth();
  // Use override projectId if provided, otherwise fall back to user's projectId
  const projectId = overrideProjectId ?? user?.projectId;

  const [tools, setTools] = useState<Record<string, ToolConfig>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetchKey, setFetchKey] = useState(0);

  const refetch = useCallback(() => setFetchKey((k) => k + 1), []);

  useEffect(() => {
    // Clear stale state when projectId becomes undefined
    if (!projectId) {
      setTools({});
      setIsLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    (async () => {
      try {
        const res = await apiFetch(`/api/projects/${encodeURIComponent(projectId)}/settings`);
        if (cancelled) return;

        if (!res.ok) {
          // 403 = no permission → treat as empty (user might not have integration:use_tools)
          if (res.status === 403) {
            setTools({});
            return;
          }
          throw new Error(`Failed to fetch project settings: ${res.status}`);
        }

        const data: ToolSettingsResponse = await res.json();
        if (cancelled) return;

        const toolMap: Record<string, ToolConfig> = {};
        for (const tool of data.tools ?? []) {
          toolMap[tool.toolId] = {
            toolId: tool.toolId,
            ready: tool.ready === true,
            config: tool.config ?? {},
            secretKeys: tool.secretKeys ?? [],
            hasSecrets: tool.hasSecrets ?? false,
          };
        }
        setTools(toolMap);
      } catch (err: any) {
        if (cancelled) return;
        console.warn('[useProjectToolConfig] Error fetching settings:', err);
        setError(err?.message || 'Failed to load project tool settings');
        setTools({});
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [projectId, fetchKey]);

  return { tools, isLoading, error, refetch };
}
