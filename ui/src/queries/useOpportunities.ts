import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import { searchOpportunities, getOpportunity, getTargetOpportunities } from '@/api/opportunities';
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
