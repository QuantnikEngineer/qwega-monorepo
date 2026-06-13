/**
 * Session-Scoped Configuration Store
 * ====================================
 * Allows per-session override of environment variables (repo URL, git credentials, etc.)
 * so that each user/project session can have its own configuration without
 * modifying global env vars.
 *
 * Priority: session config > environment variable > default
 *
 * Security:
 * - Configs are stored in-memory only (never persisted to disk)
 * - Auto-expire after SESSION_CONFIG_TTL_MS
 * - Git tokens are never logged
 */

export type SessionConfig = {
  /** Remote git repository URL (overrides REPO_LOCK_REMOTE_URL) */
  repoRemoteUrl?: string;
  /** Git username for authentication (overrides REPO_LOCK_GIT_USERNAME) */
  gitUsername?: string;
  /** Git PAT/token for authentication (overrides REPO_LOCK_GIT_TOKEN) */
  gitToken?: string;
  /** Root directory for repo operations (overrides REPO_LOCK_ROOT_DIR) */
  repoRootDir?: string;
  /** Commit author name (overrides REPO_LOCK_GIT_COMMIT_AUTHOR_NAME) */
  commitAuthorName?: string;
  /** Commit author email (overrides REPO_LOCK_GIT_COMMIT_AUTHOR_EMAIL) */
  commitAuthorEmail?: string;
  /** Default model ID (overrides DROID_MODEL_ID) */
  modelId?: string;
  /** Default reasoning level (overrides DROID_REASONING) */
  reasoning?: string;
};

type StoredSessionConfig = {
  config: SessionConfig;
  createdAt: number;
  lastAccessed: number;
};

const SESSION_CONFIG_TTL_MS = 2 * 60 * 60 * 1000; // 2 hours
const CLEANUP_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

const store = new Map<string, StoredSessionConfig>();

// Periodic cleanup of expired sessions
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of store) {
    if (now - entry.lastAccessed > SESSION_CONFIG_TTL_MS) {
      store.delete(key);
    }
  }
}, CLEANUP_INTERVAL_MS);

/**
 * Set session-scoped configuration. Merges with any existing config for this session.
 */
export function setSessionConfig(sessionId: string, config: SessionConfig): void {
  const existing = store.get(sessionId);
  const merged: SessionConfig = existing ? { ...existing.config, ...config } : { ...config };

  // Strip undefined/null values
  for (const key of Object.keys(merged) as (keyof SessionConfig)[]) {
    if (merged[key] === undefined || merged[key] === null || merged[key] === "") {
      delete merged[key];
    }
  }

  store.set(sessionId, {
    config: merged,
    createdAt: existing?.createdAt ?? Date.now(),
    lastAccessed: Date.now(),
  });
}

/**
 * Get session-scoped configuration. Returns empty object if no config set.
 */
export function getSessionConfig(sessionId: string): SessionConfig {
  const entry = store.get(sessionId);
  if (!entry) return {};
  entry.lastAccessed = Date.now();
  return entry.config;
}

/**
 * Delete session configuration (e.g. on session end).
 */
export function clearSessionConfig(sessionId: string): void {
  store.delete(sessionId);
}

/**
 * Resolve a config value: session config takes priority over env var.
 */
export function resolveConfigValue(
  sessionId: string | undefined,
  sessionKey: keyof SessionConfig,
  envKey: string,
  fallback?: string
): string {
  if (sessionId) {
    const sessionVal = getSessionConfig(sessionId)?.[sessionKey];
    if (typeof sessionVal === "string" && sessionVal.trim()) {
      return sessionVal.trim();
    }
  }
  const envVal = process.env[envKey]?.trim();
  if (envVal) return envVal;
  return fallback ?? "";
}

/**
 * Get a safe summary of session config (tokens redacted) for logging.
 */
export function getSessionConfigSummary(sessionId: string): Record<string, string> {
  const config = getSessionConfig(sessionId);
  const summary: Record<string, string> = {};
  for (const [key, value] of Object.entries(config)) {
    if (key.toLowerCase().includes("token") || key.toLowerCase().includes("pat")) {
      summary[key] = value ? "<redacted>" : "<not set>";
    } else {
      summary[key] = value || "<not set>";
    }
  }
  return summary;
}
