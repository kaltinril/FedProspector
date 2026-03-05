import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import { searchAwards, getAward, getBurnRate } from '@/api/awards';
import type { AwardSearchParams } from '@/types/api';

export function useAwardSearch(params: AwardSearchParams) {
  return useQuery({
    queryKey: queryKeys.awards.list(params as Record<string, unknown>),
    queryFn: () => searchAwards(params),
    staleTime: 3 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useAward(contractId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.awards.detail(contractId),
    queryFn: () => getAward(contractId),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}

export function useBurnRate(contractId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.awards.burnRate(contractId),
    queryFn: () => getBurnRate(contractId),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}
