// Auth token store — read on every request, set by login/register, cleared
// by logout. localStorage so it survives a tab reload.
const TOKEN_KEY = 'wega.auth.token';
export const authToken = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

async function req(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  const tok = authToken.get();
  if (tok) headers.Authorization = `Bearer ${tok}`;
  const res = await fetch(`/api${path}`, { ...opts, headers });
  if (res.status === 401) {
    // Session expired or token revoked — clear local state and let the
    // app shell push the user back to the login screen.
    authToken.clear();
    window.dispatchEvent(new CustomEvent('wega:auth-expired'));
  }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
  return res.json();
}

async function reqOrEmpty(path) {
  try { return await req(path); } catch { return null; }
}

export const api = {
  // Auth ---------------------------------------------------------------
  register: (data) => req('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login:    (data) => req('/auth/login',    { method: 'POST', body: JSON.stringify(data) }),
  logout:   () => req('/auth/logout', { method: 'POST' }).catch(() => null),
  me:       () => reqOrEmpty('/auth/me'),

  listPhases: (projectId) => reqOrEmpty(`/phases/${projectId}`),
  // scope: 'own' (default) | 'all'. 'all' only honored when the caller is an
  // admin; the backend silently downgrades it otherwise.
  listProjects: ({ scope = 'own' } = {}) =>
    req(scope === 'all' ? '/projects?scope=all' : '/projects'),
  createProject: (data) => req('/projects', { method: 'POST', body: JSON.stringify(data) }),
  updateProject: (id, data) => req(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteProject: (id) => req(`/projects/${id}`, { method: 'DELETE' }),
  resetSession: (id) => req(`/projects/${id}/reset-session`, { method: 'POST' }),
  getMessages: (id) => req(`/projects/${id}/messages`),

  listSkills: (projectId) => req(`/skills/${projectId}`),
  getSkill: (projectId, name) => req(`/skills/${projectId}/${name}`),
  saveSkill: (projectId, name, content) =>
    req(`/skills/${projectId}/${name}`, { method: 'PUT', body: JSON.stringify({ content }) }),
  deleteSkill: (projectId, name) => req(`/skills/${projectId}/${name}`, { method: 'DELETE' }),

  getSettings: (projectId) => req(`/settings/${projectId}`),
  saveSettings: (projectId, data) =>
    req(`/settings/${projectId}`, { method: 'PUT', body: JSON.stringify(data) }),
  getHooks: (projectId) => req(`/settings/${projectId}/hooks`),
  saveHooks: (projectId, hooks) =>
    req(`/settings/${projectId}/hooks`, { method: 'PUT', body: JSON.stringify(hooks) }),

  inheritedSkills: () => req('/inherited/skills'),
  inheritedMcp: () => req('/inherited/mcp'),
  lastSessionInit: (projectId) => req(`/session-info/${projectId}/last-init`),

  uploadFile: async (projectId, file) => {
    const fd = new FormData();
    fd.append('file', file);
    // Don't set Content-Type — the browser fills it in with the correct
    // multipart boundary. But we DO need to forward the auth token the
    // same way req() does, otherwise /api/uploads (mounted behind
    // requireAuth) 401s every call.
    const headers = {};
    const tok = authToken.get();
    if (tok) headers.Authorization = `Bearer ${tok}`;
    const r = await fetch(`/api/uploads/${projectId}`, { method: 'POST', body: fd, headers });
    if (r.status === 401) {
      authToken.clear();
      window.dispatchEvent(new CustomEvent('wega:auth-expired'));
    }
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
    return r.json();
  },
  listUploads: (projectId) => req(`/uploads/${projectId}`),
  deleteUpload: (projectId, name) =>
    req(`/uploads/${projectId}/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  // Authenticated download. A plain <a href> doesn't carry the Bearer
  // token, so /api/uploads/.../raw (behind requireAuth) would 401 and
  // the browser would save the JSON error body as `raw.json`. Fetch
  // the file ourselves with the header set, then trigger the save via
  // a blob URL + synthesized anchor click.
  downloadUpload: async (projectId, storedName, displayName) => {
    const tok = authToken.get();
    const headers = tok ? { Authorization: `Bearer ${tok}` } : {};
    const r = await fetch(`/api/uploads/${projectId}/${encodeURIComponent(storedName)}/raw`, { headers });
    if (r.status === 401) {
      authToken.clear();
      window.dispatchEvent(new CustomEvent('wega:auth-expired'));
    }
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = displayName || storedName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  // Admin overview. 403 unless me().user.isAdmin === true. Single fat call
  // that returns users + projects + summary so the panel can render one shot.
  adminOverview: () => req('/admin/overview'),

  // Admin user deletion. Body:
  //   { disposition: 'transfer' | 'delete', transferToUserId?: number }
  // disposition is only required when the user owns ≥1 project — the
  // server returns 400 with the project count in the error if missing.
  adminDeleteUser: (userId, body = {}) =>
    req(`/admin/users/${userId}`, { method: 'DELETE', body: JSON.stringify(body) }),
  adminRestartBackend: () => req('/admin/restart/backend', { method: 'POST' }),
  adminRestartFrontend: () => req('/admin/restart/frontend', { method: 'POST' }),

  // Context Fabric — the RAG knowledge surface.
  contextHealth: () => req('/context/health'),
  listContextSources: ({ scope, projectId }) =>
    req(`/context/sources?scope=${encodeURIComponent(scope)}${projectId ? `&projectId=${projectId}` : ''}`),
  getContextSource: (id) => req(`/context/sources/${id}`),
  addContextSource: (data) => req('/context/sources', { method: 'POST', body: JSON.stringify(data) }),
  updateContextSource: (id, patch) => req(`/context/sources/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  deleteContextSource: (id) => req(`/context/sources/${id}`, { method: 'DELETE' }),
  ingestContextSource: (id) => req(`/context/sources/${id}/ingest`, { method: 'POST' }),
  queryContext: (data) => req('/context/query', { method: 'POST', body: JSON.stringify(data) }),
  reposAvailableForContext: (projectId) => req(`/context/repos-available?projectId=${projectId}`),
  bulkAddContextSources: (sources) => req('/context/sources/bulk', { method: 'POST', body: JSON.stringify({ sources }) }),
  autoInitContext: (projectId) => req(`/context/auto-init?projectId=${projectId}`, { method: 'POST' }),
  // Quantnik Brain — RAG-grounded conversational Q&A. Returns { answer,
  // citations[], usage, costUsd, model, via }. Optional history is the
  // prior multi-turn exchange; pass the whole local conversation each call.
  askQuantnikBrain: ({ scope, projectId, question, topK, model, history, userName }) =>
    req('/context/ask', { method: 'POST', body: JSON.stringify({ scope, projectId, question, topK, model, history, userName }) }),

  listRepos: (projectId) => req(`/repos/${projectId}`),
  addRepo: (projectId, data) =>
    req(`/repos/${projectId}`, { method: 'POST', body: JSON.stringify(data) }),
  deleteRepo: (projectId, repoId) =>
    req(`/repos/${projectId}/${repoId}`, { method: 'DELETE' }),
  cloneRepo: (projectId, repoId) =>
    req(`/repos/${projectId}/${repoId}/clone`, { method: 'POST' }),
  repoTree: (projectId, repoId) => req(`/repos/${projectId}/${repoId}/tree`),

  listMcp: (projectId) => req(`/mcp/${projectId}`),
  addMcp: (projectId, name, config) =>
    req(`/mcp/${projectId}`, { method: 'POST', body: JSON.stringify({ name, config }) }),
  updateMcp: (projectId, name, config) =>
    req(`/mcp/${projectId}/${name}`, { method: 'PUT', body: JSON.stringify(config) }),
  deleteMcp: (projectId, name) =>
    req(`/mcp/${projectId}/${name}`, { method: 'DELETE' }),

  getAtlassianConfig: (projectId) => req(`/atlassian/${projectId}/config`),
  saveAtlassianConfig: (projectId, data) =>
    req(`/atlassian/${projectId}/config`, { method: 'PUT', body: JSON.stringify(data) }),
  getAtlassianArtifacts: (projectId) => req(`/atlassian/${projectId}/artifacts`),

  getLlmConfig: (projectId) => req(`/llm/${projectId}`),
  saveLlmConfig: (projectId, data) =>
    req(`/llm/${projectId}`, { method: 'PUT', body: JSON.stringify(data) }),

  getCodeStats: (projectId) => req(`/code-stats/${projectId}`),
};
