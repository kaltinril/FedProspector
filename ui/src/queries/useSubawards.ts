import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import { searchTeamingPartners } from '@/api/subawards';
import type { TeamingPartnerSearchParams } from '@/types/api';

export function useTeamingPartnerSearch(params: TeamingPartnerSearchParams) {
  return useQuery({
    queryKey: queryKeys.subawards.teamingPartners(params as Record<string, unknown>),
    queryFn: () => searchTeamingPartners(params),
    staleTime: 3 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}
