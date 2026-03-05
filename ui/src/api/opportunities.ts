import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  OpportunitySearchResult,
  OpportunitySearchParams,
  OpportunityDetail,
  TargetOpportunityDto,
  TargetSearchParams,
} from '@/types/api';

export function searchOpportunities(
  params: OpportunitySearchParams,
): Promise<PagedResponse<OpportunitySearchResult>> {
  return apiClient.get('/opportunities', { params }).then((r) => r.data);
}

export function getOpportunity(noticeId: string): Promise<OpportunityDetail> {
  return apiClient.get(`/opportunities/${encodeURIComponent(noticeId)}`).then((r) => r.data);
}

export function getTargetOpportunities(
  params: TargetSearchParams,
): Promise<PagedResponse<TargetOpportunityDto>> {
  return apiClient.get('/opportunities/targets', { params }).then((r) => r.data);
}

export function exportOpportunities(params: OpportunitySearchParams): Promise<Blob> {
  return apiClient
    .get('/opportunities/export', { params, responseType: 'blob' })
    .then((r) => r.data);
}
