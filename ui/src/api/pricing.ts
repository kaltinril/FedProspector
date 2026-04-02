import apiClient from './client';
import type {
  CanonicalCategory,
  RateHeatmapCell,
  RateDistribution,
  PriceToWinRequest,
  PriceToWinResponse,
  SubBenchmark,
  SubRatio,
  RateTrend,
  EscalationForecast,
  IgceRequest,
  IgceResponse,
} from '@/types/api';

export function getCanonicalCategories(group?: string): Promise<CanonicalCategory[]> {
  return apiClient.get('/pricing/labor-categories', { params: { group } }).then((r) => r.data);
}

export function searchLaborCategories(query: string): Promise<CanonicalCategory[]> {
  return apiClient.get('/pricing/labor-categories/search', { params: { q: query } }).then((r) => r.data);
}

export function getRateHeatmap(params: {
  categoryGroup?: string;
  worksite?: string;
  educationLevel?: string;
}): Promise<RateHeatmapCell[]> {
  return apiClient.get('/pricing/rate-heatmap', { params }).then((r) => r.data);
}

export function getRateDistribution(canonicalId: number): Promise<RateDistribution> {
  return apiClient.get(`/pricing/rate-distribution/${canonicalId}`).then((r) => r.data);
}

export function estimatePriceToWin(request: PriceToWinRequest): Promise<PriceToWinResponse> {
  return apiClient.post('/pricing/price-to-win', request).then((r) => r.data);
}

export function getSubBenchmarks(params: {
  naicsCode?: string;
  agencyName?: string;
}): Promise<SubBenchmark[]> {
  return apiClient.get('/pricing/sub-benchmarks', { params }).then((r) => r.data);
}

export function getSubRatios(naicsCode?: string): Promise<SubRatio[]> {
  return apiClient.get('/pricing/sub-ratios', { params: { naicsCode } }).then((r) => r.data);
}

export function getRateTrends(canonicalId: number, years?: number): Promise<RateTrend[]> {
  return apiClient.get('/pricing/rate-trends', { params: { canonicalId, years } }).then((r) => r.data);
}

export function getEscalationForecast(canonicalId: number, years?: number): Promise<EscalationForecast[]> {
  return apiClient.get(`/pricing/escalation-forecast/${canonicalId}`, { params: { years } }).then((r) => r.data);
}

export function estimateIgce(request: IgceRequest): Promise<IgceResponse> {
  return apiClient.post('/pricing/igce-estimate', request).then((r) => r.data);
}
