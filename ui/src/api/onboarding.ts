import apiClient from './client';
import type {
  ProfileCompletenessDto,
  UeiImportResultDto,
  CertificationAlertDto,
  SizeStandardAlertDto,
  PastPerformanceRelevanceDto,
  PortfolioGapDto,
  OrganizationPscDto,
} from '@/types/onboarding';

export function getProfileCompleteness(): Promise<ProfileCompletenessDto> {
  return apiClient.get('/onboarding/profile-completeness').then((r) => r.data);
}

export function importUei(uei: string): Promise<UeiImportResultDto> {
  return apiClient.post('/onboarding/import-uei', { uei }).then((r) => r.data);
}

export function getCertificationAlerts(): Promise<CertificationAlertDto[]> {
  return apiClient.get('/onboarding/certification-alerts').then((r) => r.data);
}

export function getSizeStandardAlerts(): Promise<SizeStandardAlertDto[]> {
  return apiClient.get('/onboarding/size-standard-alerts').then((r) => r.data);
}

export function getPastPerformanceRelevance(
  noticeId?: string,
): Promise<PastPerformanceRelevanceDto[]> {
  return apiClient
    .get('/onboarding/past-performance-relevance', {
      params: noticeId ? { noticeId } : undefined,
    })
    .then((r) => r.data);
}

export function getPortfolioGaps(): Promise<PortfolioGapDto[]> {
  return apiClient.get('/onboarding/portfolio-gaps').then((r) => r.data);
}

export function getPscCodes(): Promise<OrganizationPscDto[]> {
  return apiClient.get('/onboarding/psc-codes').then((r) => r.data);
}

export function addPscCode(pscCode: string): Promise<OrganizationPscDto> {
  return apiClient.post('/onboarding/psc-codes', { pscCode }).then((r) => r.data);
}

export function deletePscCode(id: number): Promise<void> {
  return apiClient.delete(`/onboarding/psc-codes/${id}`).then(() => undefined);
}
