import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  searchOpportunities,
  getOpportunity,
  getTargetOpportunities,
  ignoreOpportunity,
  unignoreOpportunity,
  getIgnoredOpportunityIds,
} from '@/api/opportunities';
import type { OpportunitySearchParams, TargetSearchParams } from '@/types/api';

export function useOpportunitySearch(params: OpportunitySearchParams) {
  return useQuery({
    queryKey: queryKeys.opportunities.list(params as Record<string, unknown>),
    queryFn: () => searchOpportunities(params),
    staleTime: 3 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useOpportunity(noticeId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.opportunities.detail(noticeId),
    queryFn: () => getOpportunity(noticeId),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}

export function useTargetOpportunities(params: TargetSearchParams) {
  return useQuery({
    queryKey: queryKeys.opportunities.targets(params as Record<string, unknown>),
    queryFn: () => getTargetOpportunities(params),
    staleTime: 3 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useIgnoredOpportunityIds() {
  return useQuery({
    queryKey: queryKeys.opportunities.ignoredIds(),
    queryFn: getIgnoredOpportunityIds,
    staleTime: 5 * 60 * 1000,
  });
}

export function useIgnoreOpportunity() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ noticeId, reason }: { noticeId: string; reason?: string }) =>
      ignoreOpportunity(noticeId, reason),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.opportunities.all });
    },
  });
}

export function useUnignoreOpportunity() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (noticeId: string) => unignoreOpportunity(noticeId),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.opportunities.all });
    },
  });
}
