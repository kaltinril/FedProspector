import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  EntitySearchResult,
  EntitySearchParams,
  EntityDetail,
  CompetitorProfileDto,
  ExclusionCheckDto,
} from '@/types/api';

export function searchEntities(
  params: EntitySearchParams,
): Promise<PagedResponse<EntitySearchResult>> {
  return apiClient.get('/entities', { params }).then((r) => r.data);
}

export function getEntity(uei: string): Promise<EntityDetail> {
  return apiClient.get(`/entities/${encodeURIComponent(uei)}`).then((r) => r.data);
}

export function getCompetitorProfile(uei: string): Promise<CompetitorProfileDto> {
  return apiClient
    .get(`/entities/${encodeURIComponent(uei)}/competitor-profile`)
    .then((r) => r.data);
}

export function getExclusionCheck(uei: string): Promise<ExclusionCheckDto> {
  return apiClient
    .get(`/entities/${encodeURIComponent(uei)}/exclusion-check`)
    .then((r) => r.data);
}
