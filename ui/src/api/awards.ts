import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  AwardSearchResult,
  AwardSearchParams,
  AwardDetail,
  BurnRateDto,
  MarketShareDto,
} from '@/types/api';

export function searchAwards(
  params: AwardSearchParams,
): Promise<PagedResponse<AwardSearchResult>> {
  return apiClient.get('/awards', { params }).then((r) => r.data);
}

export function getAward(contractId: string): Promise<AwardDetail> {
  return apiClient.get(`/awards/${encodeURIComponent(contractId)}`).then((r) => r.data);
}

export function getBurnRate(contractId: string): Promise<BurnRateDto> {
  return apiClient.get(`/awards/${encodeURIComponent(contractId)}/burn-rate`).then((r) => r.data);
}

export function getMarketShare(naicsCode: string, limit = 10): Promise<MarketShareDto[]> {
  return apiClient.get('/awards/market-share', { params: { naicsCode, limit } }).then((r) => r.data);
}
