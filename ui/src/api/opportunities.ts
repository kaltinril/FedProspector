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
  AnalysisEstimateDto,
  FetchDescriptionResponse,
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

const BATCH_PWIN_CHUNK_SIZE = 25;

export async function fetchBatchPWin(noticeIds: string[]): Promise<BatchPWinResponse> {
  if (noticeIds.length <= BATCH_PWIN_CHUNK_SIZE) {
    return apiClient.post('/opportunities/pwin/batch', { noticeIds }).then((r) => r.data);
  }

  // Split into chunks and fetch in parallel
  const chunks: string[][] = [];
  for (let i = 0; i < noticeIds.length; i += BATCH_PWIN_CHUNK_SIZE) {
    chunks.push(noticeIds.slice(i, i + BATCH_PWIN_CHUNK_SIZE));
  }

  const responses = await Promise.all(
    chunks.map((chunk) =>
      apiClient.post('/opportunities/pwin/batch', { noticeIds: chunk }).then((r) => r.data as BatchPWinResponse),
    ),
  );

  // Merge all results into a single response
  const merged: BatchPWinResponse = { results: {} };
  for (const resp of responses) {
    Object.assign(merged.results, resp.results);
  }
  return merged;
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

export function getAnalysisStatus(noticeId: string): Promise<LoadRequestStatusDto> {
  return apiClient.get(`/opportunities/${encodeURIComponent(noticeId)}/analyze/status`).then((r) => r.data);
}

export function getAnalysisEstimate(noticeId: string, model: string = 'haiku'): Promise<AnalysisEstimateDto> {
  return apiClient.get(`/opportunities/${encodeURIComponent(noticeId)}/analyze/estimate`, { params: { model } }).then((r) => r.data);
}

export function fetchDescription(noticeId: string): Promise<FetchDescriptionResponse> {
  return apiClient.post(`/opportunities/${encodeURIComponent(noticeId)}/fetch-description`).then((r) => r.data);
}
