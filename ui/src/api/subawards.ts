import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type { TeamingPartnerDto, TeamingPartnerSearchParams } from '@/types/api';

export function searchTeamingPartners(
  params: TeamingPartnerSearchParams,
): Promise<PagedResponse<TeamingPartnerDto>> {
  return apiClient.get('/subawards/teaming-partners', { params }).then((r) => r.data);
}
