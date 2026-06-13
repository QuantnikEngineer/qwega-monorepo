/**
 * Agent Access Hooks
 *
 * TanStack Query hooks for agent catalog and role-agent management.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchMyAgents,
  fetchAgentCatalog,
  fetchRoleAgents,
  updateRoleAgents,
  fetchProjectAgents,
  updateProjectRoleAgents,
  resetProjectRoleAgents,
} from '../api/adminApi';

export function useMyAgents() {
  return useQuery({ queryKey: ['admin', 'my-agents'], queryFn: fetchMyAgents });
}

export function useAgentCatalog() {
  return useQuery({ queryKey: ['admin', 'agent-catalog'], queryFn: fetchAgentCatalog });
}

export function useRoleAgents(roleId: string | null) {
  return useQuery({
    queryKey: ['admin', 'role-agents', roleId],
    queryFn: () => fetchRoleAgents(roleId!),
    enabled: !!roleId,
  });
}

export function useUpdateRoleAgents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ roleId, agentIds }: { roleId: string; agentIds: string[] }) =>
      updateRoleAgents(roleId, agentIds),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['admin', 'role-agents', variables.roleId] });
      qc.invalidateQueries({ queryKey: ['admin', 'my-agents'] });
    },
  });
}

// ── Project-Level Agent Access ──────────────────────────────────

export function useProjectAgents(projectId: string | null) {
  return useQuery({
    queryKey: ['admin', 'project-agents', projectId],
    queryFn: () => fetchProjectAgents(projectId!),
    enabled: !!projectId,
  });
}

export function useUpdateProjectRoleAgents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, roleId, agentIds }: { projectId: string; roleId: string; agentIds: string[] }) =>
      updateProjectRoleAgents(projectId, roleId, agentIds),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['admin', 'project-agents', variables.projectId] });
    },
  });
}

export function useResetProjectRoleAgents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, roleId }: { projectId: string; roleId: string }) =>
      resetProjectRoleAgents(projectId, roleId),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['admin', 'project-agents', variables.projectId] });
    },
  });
}
