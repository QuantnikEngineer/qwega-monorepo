/**
 * Admin API Client
 *
 * CRUD operations for admin panel: users, roles, projects.
 * Uses apiFetch for automatic Bearer token injection and 401 retry.
 */

import { apiFetch } from '../../services/apiClient';

// Types

export interface AdminUser {
  id: string;
  email: string;
  displayName: string;
  status: 'pending' | 'active' | 'suspended' | 'deactivated';
  orgId: string;
  createdAt: string;
  lastLoginAt: string | null;
  roles: Array<{ roleName: string; scopeType: string; scopeId: string | null }>;
  projects?: Array<{ id: string; name: string }>;
}

export interface CreateUserPayload {
  email: string;
  display_name: string;
  role_assignments: Array<{ role_name: string; scope_type: string; scope_id?: string }>;
}

export interface UpdateUserPayload {
  display_name?: string;
  role_assignments?: Array<{ role_name: string; scope_type: string; scope_id?: string }>;
  status?: string;
}

export interface RoleInfo {
  id: string;
  name: string;
  description: string | null;
  capabilities: string[];
}

export interface ProjectInfo {
  id: string;
  name: string;
  slug: string;
  orgId: string;
  description: string | null;
  createdBy: string | null;
  isActive: boolean;
  openForRegistration: boolean;
  createdAt: string | null;
}

export interface ProjectMemberRole {
  roleName: string;
  assignedAt: string | null;
}

export interface ProjectMember {
  userId: string;
  email: string;
  displayName: string;
  roles: ProjectMemberRole[];
}

export interface CreateProjectPayload {
  name: string;
  description?: string;
  slug?: string;
  open_for_registration?: boolean;
}

export interface UpdateProjectPayload {
  name?: string;
  description?: string;
  open_for_registration?: boolean;
}

export interface AddMemberPayload {
  user_id: string;
  role_name: string;
}

export interface ProjectToolInfo {
  serviceId: string;
  toolId: string;
  name: string;
  icon: string | null;
  description: string | null;
  category: string | null;
  color: string | null;
  platformEnabled: boolean;
  projectEnabled: boolean;
  available: boolean;
  configured: boolean;
  config: Record<string, unknown>;
  defaultConfig: Record<string, unknown>;
  secretKeys: string[];
  hasSecrets: boolean;
}

export interface UpdateToolConfigPayload {
  config: Record<string, unknown>;
  is_enabled: boolean;
  secrets: Record<string, string>;
}

// API functions

export async function fetchUsers(): Promise<{ users: AdminUser[]; total: number }> {
  const res = await apiFetch('/api/users');
  if (!res.ok) throw new Error('Failed to fetch users');
  return res.json();
}

export async function createUser(
  data: CreateUserPayload,
): Promise<{ user: AdminUser; activation_url: string; expires_in_hours: number }> {
  const res = await apiFetch('/api/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to create user' }));
    throw new Error(err.detail || 'Failed to create user');
  }
  return res.json();
}

export async function updateUser(userId: string, data: UpdateUserPayload): Promise<AdminUser> {
  const res = await apiFetch(`/api/users/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update user' }));
    throw new Error(err.detail || 'Failed to update user');
  }
  return res.json();
}

export async function deactivateUser(userId: string): Promise<AdminUser> {
  const res = await apiFetch(`/api/users/${userId}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to deactivate user' }));
    throw new Error(err.detail || 'Failed to deactivate user');
  }
  return res.json();
}

export async function deleteUserPermanently(userId: string): Promise<void> {
  const res = await apiFetch(`/api/users/${userId}?permanent=true`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to delete user' }));
    throw new Error(err.detail || 'Failed to delete user');
  }
}

export async function reactivateUser(userId: string): Promise<AdminUser> {
  const res = await apiFetch(`/api/users/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'active' }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to reactivate user' }));
    throw new Error(err.detail || 'Failed to reactivate user');
  }
  return res.json();
}

export async function resetUserPassword(
  userId: string,
): Promise<{ activation_url: string; expires_in_hours: number }> {
  const res = await apiFetch(`/api/users/${userId}/reset-password`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset password');
  return res.json();
}

export async function resendActivation(
  userId: string,
): Promise<{ activation_url: string; expires_in_hours: number }> {
  const res = await apiFetch(`/api/users/${userId}/resend-activation`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to resend activation');
  return res.json();
}

export async function fetchRoles(): Promise<{ roles: RoleInfo[] }> {
  const res = await apiFetch('/api/roles');
  if (!res.ok) throw new Error('Failed to fetch roles');
  return res.json();
}

export async function fetchMyAgents(): Promise<{ agents: string[] }> {
  const res = await apiFetch('/api/roles/agents');
  if (!res.ok) throw new Error('Failed to fetch agent mapping');
  return res.json();
}

export async function fetchCapabilityMatrix(): Promise<{
  categories: Record<string, Array<{ name: string; roles: string[] }>>;
}> {
  const res = await apiFetch('/api/roles/capabilities');
  if (!res.ok) throw new Error('Failed to fetch capabilities');
  return res.json();
}

export async function fetchProjects(): Promise<{ projects: ProjectInfo[] }> {
  const res = await apiFetch('/api/projects');
  if (!res.ok) throw new Error('Failed to fetch projects');
  return res.json();
}

// ── Project CRUD ────────────────────────────────────────────────

export async function createProject(
  data: CreateProjectPayload,
): Promise<ProjectInfo> {
  const res = await apiFetch('/api/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to create project' }));
    throw new Error(err.detail || 'Failed to create project');
  }
  return res.json();
}

export async function updateProject(
  projectId: string,
  data: UpdateProjectPayload,
): Promise<ProjectInfo> {
  const res = await apiFetch(`/api/projects/${projectId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update project' }));
    throw new Error(err.detail || 'Failed to update project');
  }
  return res.json();
}

export async function deleteProject(projectId: string): Promise<void> {
  const res = await apiFetch(`/api/projects/${projectId}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to delete project' }));
    throw new Error(err.detail || 'Failed to delete project');
  }
}

// ── Project Members ─────────────────────────────────────────────

export async function fetchProjectMembers(
  projectId: string,
): Promise<{ members: ProjectMember[]; total: number }> {
  const res = await apiFetch(`/api/projects/${projectId}/members`);
  if (!res.ok) throw new Error('Failed to fetch project members');
  return res.json();
}

export async function addProjectMember(
  projectId: string,
  data: AddMemberPayload,
): Promise<void> {
  const res = await apiFetch(`/api/projects/${projectId}/members`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to add member' }));
    throw new Error(err.detail || 'Failed to add member');
  }
}

export async function removeProjectMember(
  projectId: string,
  userId: string,
): Promise<void> {
  const res = await apiFetch(`/api/projects/${projectId}/members/${userId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to remove member' }));
    throw new Error(err.detail || 'Failed to remove member');
  }
}

// ── Project Tool Settings ───────────────────────────────────────

export async function fetchProjectSettings(
  projectId: string,
): Promise<{ projectId: string; tools: ProjectToolInfo[] }> {
  const res = await apiFetch(`/api/projects/${projectId}/settings`);
  if (!res.ok) throw new Error('Failed to fetch project settings');
  return res.json();
}

export async function updateProjectToolConfig(
  projectId: string,
  serviceId: string,
  data: UpdateToolConfigPayload,
): Promise<void> {
  const res = await apiFetch(`/api/projects/${projectId}/settings/${serviceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to save tool config' }));
    throw new Error(err.detail || 'Failed to save tool config');
  }
}

// ── Platform Service Registry ────────────────────────────────────

export interface PlatformService {
  id: string;
  toolId: string;
  name: string;
  icon: string | null;
  description: string | null;
  category: string | null;
  color: string | null;
  defaultConfig: Record<string, unknown>;
  enabled: boolean;
}

export interface CreateServicePayload {
  tool_id: string;
  name: string;
  icon?: string;
  description?: string;
  category?: string;
  enabled?: boolean;
}

export interface UpdateServicePayload {
  name?: string;
  icon?: string;
  description?: string;
  category?: string;
  enabled?: boolean;
}

export async function fetchServices(): Promise<{ services: PlatformService[] }> {
  const res = await apiFetch('/api/services');
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to fetch services' }));
    throw new Error(err.detail || 'Failed to fetch services');
  }
  return res.json();
}

export async function createService(data: CreateServicePayload): Promise<PlatformService> {
  const res = await apiFetch('/api/services', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to create service' }));
    throw new Error(err.detail || 'Failed to create service');
  }
  return res.json();
}

export async function updateService(serviceId: string, data: UpdateServicePayload): Promise<PlatformService> {
  const res = await apiFetch(`/api/services/${serviceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update service' }));
    throw new Error(err.detail || 'Failed to update service');
  }
  return res.json();
}

// ── Agent Access Management ─────────────────────────────────────

export interface AgentCatalogEntry {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  is_active: boolean;
}

export interface RoleAgentsResponse {
  role_id: string;
  role_name: string;
  agent_ids: string[];
}

export async function fetchAgentCatalog(): Promise<{ agents: AgentCatalogEntry[] }> {
  const res = await apiFetch('/api/agents');
  if (!res.ok) throw new Error('Failed to fetch agent catalog');
  return res.json();
}

export async function fetchRoleAgents(roleId: string): Promise<RoleAgentsResponse> {
  const res = await apiFetch(`/api/agents/roles/${roleId}`);
  if (!res.ok) throw new Error('Failed to fetch role agents');
  return res.json();
}

export async function updateRoleAgents(
  roleId: string,
  agentIds: string[],
): Promise<RoleAgentsResponse> {
  const res = await apiFetch(`/api/agents/roles/${roleId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_ids: agentIds }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update agent access' }));
    throw new Error(err.detail || 'Failed to update agent access');
  }
  return res.json();
}

// ── Project-Level Agent Access Management ───────────────────────

export interface ProjectRoleAgentConfig {
  role_id: string;
  role_name: string;
  mode: 'inherit' | 'override';
  global_agent_ids: string[];
  project_agent_ids: string[] | null;
  effective_agent_ids: string[];
}

export interface ProjectAgentsResponse {
  project_id: string;
  roles: ProjectRoleAgentConfig[];
}

export async function fetchProjectAgents(projectId: string): Promise<ProjectAgentsResponse> {
  const res = await apiFetch(`/api/projects/${projectId}/agents`);
  if (!res.ok) throw new Error('Failed to fetch project agent configuration');
  return res.json();
}

export async function updateProjectRoleAgents(
  projectId: string,
  roleId: string,
  agentIds: string[],
): Promise<ProjectRoleAgentConfig> {
  const res = await apiFetch(`/api/projects/${projectId}/agents/${roleId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent_ids: agentIds }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update project agent access' }));
    throw new Error(err.detail || 'Failed to update project agent access');
  }
  return res.json();
}

export async function resetProjectRoleAgents(
  projectId: string,
  roleId: string,
): Promise<ProjectRoleAgentConfig> {
  const res = await apiFetch(`/api/projects/${projectId}/agents/${roleId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to reset project agent access' }));
    throw new Error(err.detail || 'Failed to reset project agent access');
  }
  return res.json();
}
