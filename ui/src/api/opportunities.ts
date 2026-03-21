import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  OpportunitySearchResult,
  OpportunitySearchParams,
  OpportunityDetail,
  TargetOpportunityDto,
  TargetSearchParams,
  PWinResultDto,
  QualificationCheckDto,
  IncumbentAnalysisDto,
  RecommendedOpportunityDto,
  BatchPWinResponse,
  CompetitiveLandscapeDto,
  SetAsideShiftDto,
  DocumentIntelligenceDto,
  LoadRequestStatusDto,
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

export function getPWin(noticeId: string): Promise<PWinResultDto> {
  return apiClient.get(`/opportunities/${encodeURIComponent(noticeId)}/pwin`).then((r) => r.data);
}

export function getQualification(noticeId: string): Promise<QualificationCheckDto> {
  return apiClient.get(`/opportunities/${encodeURIComponent(noticeId)}/qualification`).then((r) => r.data);
}

export function getIncumbentAnalysis(noticeId: string): Promise<IncumbentAnalysisDto> {
  return apiClient.get(`/opportunities/${encodeURIComponent(noticeId)}/incumbent`).then((r) => r.data);
}

export function getRecommendedOpportunities(limit: number = 10): Promise<RecommendedOpportunityDto[]> {
  return apiClient.get('/opportunities/recommended', { params: { limit } }).then((r) => r.data);
}

export function fetchBatchPWin(noticeIds: string[]): Promise<BatchPWinResponse> {
  return apiClient.post('/opportunities/pwin/batch', { noticeIds }).then((r) => r.data);
}

export function getCompetitiveLandscape(noticeId: string): Promise<CompetitiveLandscapeDto> {
  return apiClient.get(`/opportunities/${encodeURIComponent(noticeId)}/competitive-landscape`).then((r) => r.data);
}

export function getSetAsideShift(noticeId: string): Promise<SetAsideShiftDto> {
  return apiClient.get(`/opportunities/${encodeURIComponent(noticeId)}/set-aside-shift`).then((r) => r.data);
}

export function getDocumentIntelligence(noticeId: string): Promise<DocumentIntelligenceDto> {
  return apiClient.get(`/opportunities/${encodeURIComponent(noticeId)}/document-intelligence`).then((r) => r.data);
}

export function requestAnalysis(noticeId: string, tier: string = 'haiku'): Promise<LoadRequestStatusDto> {
  return apiClient.post(`/opportunities/${encodeURIComponent(noticeId)}/analyze?tier=${encodeURIComponent(tier)}`).then((r) => r.data);
}
