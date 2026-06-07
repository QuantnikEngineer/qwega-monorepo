async function req(path, opts = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
  return res.json();
}

export const api = {
  listProjects: () => req('/projects'),
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
    const r = await fetch(`/api/uploads/${projectId}`, { method: 'POST', body: fd });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
    return r.json();
  },
  listUploads: (projectId) => req(`/uploads/${projectId}`),
  deleteUpload: (projectId, name) =>
    req(`/uploads/${projectId}/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  uploadDownloadUrl: (projectId, name) =>
    `/api/uploads/${projectId}/${encodeURIComponent(name)}/raw`,

  listRepos: (projectId) => req(`/repos/${projectId}`),
  addRepo: (projectId, data) =>
    req(`/repos/${projectId}`, { method: 'POST', body: JSON.stringify(data) }),
  deleteRepo: (projectId, repoId) =>
    req(`/repos/${projectId}/${repoId}`, { method: 'DELETE' }),
  cloneRepo: (projectId, repoId) =>
    req(`/repos/${projectId}/${repoId}/clone`, { method: 'POST' }),

  listMcp: (projectId) => req(`/mcp/${projectId}`),
  addMcp: (projectId, name, config) =>
    req(`/mcp/${projectId}`, { method: 'POST', body: JSON.stringify({ name, config }) }),
  updateMcp: (projectId, name, config) =>
    req(`/mcp/${projectId}/${name}`, { method: 'PUT', body: JSON.stringify(config) }),
  deleteMcp: (projectId, name) =>
    req(`/mcp/${projectId}/${name}`, { method: 'DELETE' }),
};
