/**
 * Project Admin Hooks
 *
 * TanStack Query hooks for project CRUD, members, and tool settings.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  addProjectMember,
  createProject,
  deleteProject,
  fetchProjectMembers,
  fetchProjectSettings,
  fetchProjects,
  removeProjectMember,
  updateProject,
  updateProjectToolConfig,
  type CreateProjectPayload,
  type UpdateProjectPayload,
  type AddMemberPayload,
  type UpdateToolConfigPayload,
} from '../api/adminApi';

export function useProjects() {
  return useQuery({ queryKey: ['admin', 'projects'], queryFn: fetchProjects });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateProjectPayload) => createProject(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'projects'] }),
  });
}

export function useUpdateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, data }: { projectId: string; data: UpdateProjectPayload }) =>
      updateProject(projectId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'projects'] }),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) => deleteProject(projectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'projects'] }),
  });
}

// ── Members ─────────────────────────────────────────────────────

export function useProjectMembers(projectId: string | null) {
  return useQuery({
    queryKey: ['admin', 'project-members', projectId],
    queryFn: () => fetchProjectMembers(projectId!),
    enabled: !!projectId,
  });
}

export function useAddProjectMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, data }: { projectId: string; data: AddMemberPayload }) =>
      addProjectMember(projectId, data),
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ['admin', 'project-members', vars.projectId] }),
  });
}

export function useRemoveProjectMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, userId }: { projectId: string; userId: string }) =>
      removeProjectMember(projectId, userId),
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ['admin', 'project-members', vars.projectId] }),
  });
}

// ── Tool Settings ───────────────────────────────────────────────

export function useProjectSettings(projectId: string | null) {
  return useQuery({
    queryKey: ['admin', 'project-settings', projectId],
    queryFn: () => fetchProjectSettings(projectId!),
    enabled: !!projectId,
  });
}

export function useUpdateToolConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      serviceId,
      data,
    }: {
      projectId: string;
      serviceId: string;
      data: UpdateToolConfigPayload;
    }) => updateProjectToolConfig(projectId, serviceId, data),
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ['admin', 'project-settings', vars.projectId] }),
  });
}
