import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  PartnerSearchResultDto,
  PartnerSearchParams,
  PartnerRiskDto,
  PrimeSubRelationshipDto,
  TeamingNetworkNodeDto,
  MentorProtegePairDto,
  MentorProtegeSearchParams,
  PartnerGapAnalysisDto,
} from '@/types/teaming';

export function searchPartners(
  params: PartnerSearchParams,
): Promise<PagedResponse<PartnerSearchResultDto>> {
  return apiClient.get('/teaming/partners', { params }).then((r) => r.data);
}

export function getPartnerRisk(uei: string): Promise<PartnerRiskDto> {
  return apiClient
    .get(`/teaming/partners/${encodeURIComponent(uei)}/risk`)
    .then((r) => r.data);
}

export function getPartnerRelationships(
  uei: string,
  page?: number,
  pageSize?: number,
): Promise<PagedResponse<PrimeSubRelationshipDto>> {
  return apiClient
    .get(`/teaming/partners/${encodeURIComponent(uei)}/relationships`, {
      params: { page, pageSize },
    })
    .then((r) => r.data);
}

export function getPartnerNetwork(
  uei: string,
  depth?: number,
): Promise<TeamingNetworkNodeDto[]> {
  return apiClient
    .get(`/teaming/partners/${encodeURIComponent(uei)}/network`, {
      params: depth ? { depth } : undefined,
    })
    .then((r) => r.data);
}

export function searchMentorProtege(
  params: MentorProtegeSearchParams,
): Promise<PagedResponse<MentorProtegePairDto>> {
  return apiClient.get('/teaming/mentor-protege', { params }).then((r) => r.data);
}

export function getGapAnalysis(naicsCode?: string): Promise<PartnerGapAnalysisDto> {
  return apiClient
    .get('/teaming/gap-analysis', { params: naicsCode ? { naicsCode } : undefined })
    .then((r) => r.data);
}
