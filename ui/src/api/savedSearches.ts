import apiClient from './client';
import type {
  SavedSearchDto,
  CreateSavedSearchRequest,
  UpdateSavedSearchRequest,
  SavedSearchRunResultDto,
} from '@/types/api';

export function listSavedSearches(): Promise<SavedSearchDto[]> {
  return apiClient.get('/saved-searches').then((r) => r.data);
}

export function getSavedSearch(id: number): Promise<SavedSearchDto> {
  return apiClient.get(`/saved-searches/${id}`).then((r) => r.data);
}

export function createSavedSearch(data: CreateSavedSearchRequest): Promise<SavedSearchDto> {
  return apiClient.post('/saved-searches', data).then((r) => r.data);
}

export function updateSavedSearch(
  id: number,
  data: UpdateSavedSearchRequest,
): Promise<SavedSearchDto> {
  return apiClient.patch(`/saved-searches/${id}`, data).then((r) => r.data);
}

export function deleteSavedSearch(id: number): Promise<void> {
  return apiClient.delete(`/saved-searches/${id}`).then((r) => r.data);
}

export function runSavedSearch(id: number): Promise<SavedSearchRunResultDto> {
  return apiClient.post(`/saved-searches/${id}/run`).then((r) => r.data);
}
