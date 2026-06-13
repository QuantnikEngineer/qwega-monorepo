/**
 * Platform Services Hooks
 *
 * TanStack Query hooks for platform service registry CRUD.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createService,
  fetchServices,
  updateService,
  type CreateServicePayload,
  type UpdateServicePayload,
} from '../api/adminApi';

export function useServices() {
  return useQuery({ queryKey: ['admin', 'services'], queryFn: fetchServices });
}

export function useCreateService() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateServicePayload) => createService(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'services'] }),
  });
}

export function useUpdateService() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ serviceId, data }: { serviceId: string; data: UpdateServicePayload }) =>
      updateService(serviceId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'services'] }),
  });
}
