import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import { searchEntities, getEntity, getCompetitorProfile, getExclusionCheck } from '@/api/entities';
import type { EntitySearchParams } from '@/types/api';

export function useEntitySearch(params: EntitySearchParams) {
  return useQuery({
    queryKey: queryKeys.entities.list(params as Record<string, unknown>),
    queryFn: () => searchEntities(params),
    staleTime: 3 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useEntity(uei: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.entities.detail(uei),
    queryFn: () => getEntity(uei),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}

export function useCompetitorProfile(uei: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.entities.competitor(uei),
    queryFn: () => getCompetitorProfile(uei),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}

export function useExclusionCheck(uei: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.entities.exclusions(uei),
    queryFn: () => getExclusionCheck(uei),
    staleTime: 5 * 60 * 1000,
    enabled,
  });
}
