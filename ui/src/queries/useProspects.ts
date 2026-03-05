import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  searchProspects,
  getProspect,
  createProspect,
  updateProspectStatus,
  reassignProspect,
  addProspectNote,
  addTeamMember,
  removeTeamMember,
  recalculateScore,
} from '@/api/prospects';
import type {
  ProspectSearchParams,
  CreateProspectRequest,
  UpdateProspectStatusRequest,
  ReassignProspectRequest,
  CreateProspectNoteRequest,
  AddTeamMemberRequest,
} from '@/types/api';

export function useProspectSearch(params: ProspectSearchParams) {
  return useQuery({
    queryKey: queryKeys.prospects.list(params as Record<string, unknown>),
    queryFn: () => searchProspects(params),
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useProspect(id: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.prospects.detail(id),
    queryFn: () => getProspect(id),
    staleTime: 2 * 60 * 1000,
    enabled,
  });
}

export function useCreateProspect() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateProspectRequest) => createProspect(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}

export function useUpdateProspectStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateProspectStatusRequest }) =>
      updateProspectStatus(id, data),
    retry: 1,
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.detail(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
    },
  });
}

export function useReassignProspect() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ReassignProspectRequest }) =>
      reassignProspect(id, data),
    retry: 1,
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.detail(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.all });
    },
  });
}

export function useAddProspectNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CreateProspectNoteRequest }) =>
      addProspectNote(id, data),
    retry: 1,
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.detail(id) });
    },
  });
}

export function useAddTeamMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: AddTeamMemberRequest }) =>
      addTeamMember(id, data),
    retry: 1,
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.detail(id) });
    },
  });
}

export function useRemoveTeamMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, memberId }: { id: number; memberId: number }) =>
      removeTeamMember(id, memberId),
    retry: 1,
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.detail(id) });
    },
  });
}

export function useRecalculateScore() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => recalculateScore(id),
    retry: 1,
    onSuccess: (_data, id) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.prospects.detail(id) });
    },
  });
}
