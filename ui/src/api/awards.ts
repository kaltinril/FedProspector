import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  AwardSearchResult,
  AwardSearchParams,
  AwardDetailResponse,
  LoadRequestStatus,
  BurnRateDto,
  MarketShareDto,
  IntelMarketShareDto,
  ExpiringContractDto,
} from '@/types/api';

export function searchAwards(
  params: AwardSearchParams,
): Promise<PagedResponse<AwardSearchResult>> {
  return apiClient.get('/awards', { params }).then((r) => r.data);
}

export function getAward(contractId: string): Promise<AwardDetailResponse> {
  return apiClient.get(`/awards/${encodeURIComponent(contractId)}`).then((r) => r.data);
}

export function requestAwardLoad(contractId: string, tier: 'usaspending' | 'fpds' = 'usaspending'): Promise<LoadRequestStatus> {
  return apiClient.post(`/awards/${encodeURIComponent(contractId)}/load`, { tier }).then((r) => r.data);
}

export function getAwardLoadStatus(contractId: string): Promise<LoadRequestStatus> {
  return apiClient.get(`/awards/${encodeURIComponent(contractId)}/load-status`).then((r) => r.data);
}

export function getBurnRate(contractId: string): Promise<BurnRateDto> {
  return apiClient.get(`/awards/${encodeURIComponent(contractId)}/burn-rate`).then((r) => r.data);
}

export function getMarketShare(naicsCode: string, limit = 10): Promise<MarketShareDto[]> {
  return apiClient.get('/awards/market-share', { params: { naicsCode, limit } }).then((r) => r.data);
}

export function getIntelMarketShare(naicsCode: string, years: number = 3, limit: number = 10): Promise<IntelMarketShareDto> {
  return apiClient.get('/awards/market-share', { params: { naicsCode, years, limit } }).then((r) => r.data);
}

export function getExpiringContracts(params: { monthsAhead?: number; naicsCode?: string; setAsideType?: string; limit?: number; offset?: number }): Promise<ExpiringContractDto[]> {
  return apiClient.get('/awards/expiring', { params }).then((r) => r.data);
}
