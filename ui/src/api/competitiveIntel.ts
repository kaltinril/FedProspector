import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  RecompeteCandidateDto,
  RecompeteCandidateSearchParams,
  AgencyRecompetePatternDto,
  AgencyPatternSearchParams,
  AgencyBuyingPatternDto,
  CompetitorDossierDto,
  ContractingOfficeProfileDto,
  OfficeSearchParams,
} from '@/types/competitiveIntel';

export function searchRecompeteCandidates(
  params: RecompeteCandidateSearchParams,
): Promise<PagedResponse<RecompeteCandidateDto>> {
  return apiClient.get('/competitive-intel/recompete-candidates', { params }).then((r) => r.data);
}

export function getAgencyPatterns(
  params: AgencyPatternSearchParams,
): Promise<AgencyRecompetePatternDto[]> {
  return apiClient.get('/competitive-intel/agency-patterns', { params }).then((r) => r.data);
}

export function getAgencyBuyingPatterns(
  agencyCode: string,
  year?: number,
): Promise<AgencyBuyingPatternDto[]> {
  return apiClient
    .get(`/competitive-intel/agency-patterns/${encodeURIComponent(agencyCode)}`, {
      params: year ? { year } : undefined,
    })
    .then((r) => r.data);
}

export function getCompetitorDossier(uei: string): Promise<CompetitorDossierDto> {
  return apiClient
    .get(`/competitive-intel/competitor/${encodeURIComponent(uei)}`)
    .then((r) => r.data);
}

export function searchOffices(
  params: OfficeSearchParams,
): Promise<PagedResponse<ContractingOfficeProfileDto>> {
  return apiClient.get('/competitive-intel/offices', { params }).then((r) => r.data);
}

export function getOfficeProfile(officeCode: string): Promise<ContractingOfficeProfileDto> {
  return apiClient
    .get(`/competitive-intel/offices/${encodeURIComponent(officeCode)}`)
    .then((r) => r.data);
}
