import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  getEtlStatus,
  listUsers,
  updateUser,
  resetUserPassword,
  createOrganization,
  createOrganizationOwner,
  createUserForOrg,
  listOrganizations,
  getLoadHistory,
  getHealth,
} from '@/api/admin';
import type { UpdateUserRequest, CreateOrganizationRequest, CreateOwnerRequest, LoadHistoryParams } from '@/types/api';

export function useEtlStatus() {
  return useQuery({
    queryKey: queryKeys.admin.etlStatus,
    queryFn: getEtlStatus,
    staleTime: 60 * 1000,
    refetchOnWindowFocus: true,
  });
}

export function useAdminUsers(params?: { page?: number; pageSize?: number }) {
  return useQuery({
    queryKey: queryKeys.admin.users(params as Record<string, unknown>),
    queryFn: () => listUsers(params),
    staleTime: 2 * 60 * 1000,
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateUserRequest }) => updateUser(id, data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.admin.all });
    },
  });
}

export function useResetUserPassword() {
  return useMutation({
    mutationFn: (id: number) => resetUserPassword(id),
    retry: 0,
  });
}

export function useListOrganizations() {
  return useQuery({
    queryKey: queryKeys.admin.organizations,
    queryFn: () => listOrganizations(),
    staleTime: 60_000,
  });
}

export function useCreateOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateOrganizationRequest) => createOrganization(data),
    retry: 0,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.admin.organizations });
    },
  });
}

export function useCreateOrganizationOwner() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, data }: { orgId: number; data: CreateOwnerRequest }) =>
      createOrganizationOwner(orgId, data),
    retry: 0,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.admin.organizations });
    },
  });
}

export function useCreateUserForOrg() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orgId, data }: { orgId: number; data: { email: string; displayName: string; password: string; orgRole: string } }) =>
      createUserForOrg(orgId, data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.admin.organizations });
    },
  });
}

export function useLoadHistory(params?: LoadHistoryParams) {
  return useQuery({
    queryKey: queryKeys.admin.loadHistory(params as Record<string, unknown>),
    queryFn: () => getLoadHistory(params),
    staleTime: 60 * 1000,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.admin.health,
    queryFn: getHealth,
    staleTime: 30 * 1000,
    refetchOnWindowFocus: true,
  });
}
