import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type { TeamingPartnerDto, TeamingPartnerSearchParams, SubawardDetailDto } from '@/types/api';

export function searchTeamingPartners(
  params: TeamingPartnerSearchParams,
): Promise<PagedResponse<TeamingPartnerDto>> {
  return apiClient.get('/subawards/teaming-partners', { params }).then((r) => r.data);
}

export function getSubawardsByPrime(primePiid: string): Promise<SubawardDetailDto[]> {
  return apiClient.get(`/subawards/by-prime/${encodeURIComponent(primePiid)}`).then((r) => r.data);
}
