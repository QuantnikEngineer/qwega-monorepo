/**
 * Role Admin Hooks
 *
 * TanStack Query hooks for roles and capability matrix.
 */

import { useQuery } from '@tanstack/react-query';
import { fetchRoles, fetchCapabilityMatrix } from '../api/adminApi';

export function useRoles() {
  return useQuery({ queryKey: ['admin', 'roles'], queryFn: fetchRoles, staleTime: 5 * 60 * 1000 });
}

export function useCapabilityMatrix() {
  return useQuery({ queryKey: ['admin', 'capabilities'], queryFn: fetchCapabilityMatrix, staleTime: 5 * 60 * 1000 });
}
