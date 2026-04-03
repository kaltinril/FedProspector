import apiClient from './client';
import type {
  SimilarOpportunityDto,
  DataQualityDashboardDto,
  DataFreshnessDto,
  DataCompletenessDto,
  CrossSourceValidationDto,
  ProspectCompetitorSummaryDto,
} from '@/types/insights';

export function getSimilarOpportunities(
  noticeId: string,
  maxResults = 20,
): Promise<SimilarOpportunityDto[]> {
  return apiClient
    .get(`/insights/similar-opportunities/${encodeURIComponent(noticeId)}`, {
      params: { maxResults },
    })
    .then((r) => r.data);
}

export function getDataQualityDashboard(): Promise<DataQualityDashboardDto> {
  return apiClient.get('/insights/data-quality').then((r) => r.data);
}

export function getDataFreshness(): Promise<DataFreshnessDto[]> {
  return apiClient.get('/insights/data-quality/freshness').then((r) => r.data);
}

export function getDataCompleteness(): Promise<DataCompletenessDto[]> {
  return apiClient.get('/insights/data-quality/completeness').then((r) => r.data);
}

export function getCrossSourceValidation(): Promise<CrossSourceValidationDto[]> {
  return apiClient.get('/insights/data-quality/validation').then((r) => r.data);
}

export function getProspectCompetitors(
  prospectIds: number[],
): Promise<ProspectCompetitorSummaryDto[]> {
  return apiClient
    .get('/insights/prospect-competitors', {
      params: { prospectIds: prospectIds.join(',') },
    })
    .then((r) => r.data);
}

export function getProspectCompetitorSummary(
  prospectId: number,
): Promise<ProspectCompetitorSummaryDto> {
  return apiClient
    .get(`/insights/prospect-competitors/${prospectId}`)
    .then((r) => r.data);
}
