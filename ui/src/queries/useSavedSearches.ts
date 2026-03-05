import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  listSavedSearches,
  getSavedSearch,
  createSavedSearch,
  updateSavedSearch,
  deleteSavedSearch,
  runSavedSearch,
} from '@/api/savedSearches';
import type { CreateSavedSearchRequest, UpdateSavedSearchRequest } from '@/types/api';

export function useSavedSearches() {
  return useQuery({
    queryKey: queryKeys.savedSearches.list,
    queryFn: listSavedSearches,
    staleTime: 2 * 60 * 1000,
  });
}

export function useSavedSearch(id: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.savedSearches.detail(id),
    queryFn: () => getSavedSearch(id),
    staleTime: 2 * 60 * 1000,
    enabled,
  });
}

export function useCreateSavedSearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateSavedSearchRequest) => createSavedSearch(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.savedSearches.all });
    },
  });
}

export function useUpdateSavedSearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateSavedSearchRequest }) =>
      updateSavedSearch(id, data),
    retry: 1,
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.savedSearches.detail(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.savedSearches.list });
    },
  });
}

export function useDeleteSavedSearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteSavedSearch(id),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.savedSearches.all });
    },
  });
}

export function useRunSavedSearch() {
  return useMutation({
    mutationFn: (id: number) => runSavedSearch(id),
    retry: 1,
  });
}
