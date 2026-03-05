import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  ProspectListDto,
  ProspectSearchParams,
  ProspectDetailDto,
  ProspectNoteDto,
  ProspectTeamMemberDto,
  ScoreBreakdownDto,
  CreateProspectRequest,
  UpdateProspectStatusRequest,
  ReassignProspectRequest,
  CreateProspectNoteRequest,
  AddTeamMemberRequest,
} from '@/types/api';

export function searchProspects(
  params: ProspectSearchParams,
): Promise<PagedResponse<ProspectListDto>> {
  return apiClient.get('/prospects', { params }).then((r) => r.data);
}

export function getProspect(id: number): Promise<ProspectDetailDto> {
  return apiClient.get(`/prospects/${id}`).then((r) => r.data);
}

export function createProspect(data: CreateProspectRequest): Promise<ProspectDetailDto> {
  return apiClient.post('/prospects', data).then((r) => r.data);
}

export function updateProspectStatus(
  id: number,
  data: UpdateProspectStatusRequest,
): Promise<void> {
  return apiClient.patch(`/prospects/${id}/status`, data).then((r) => r.data);
}

export function reassignProspect(id: number, data: ReassignProspectRequest): Promise<void> {
  return apiClient.patch(`/prospects/${id}/reassign`, data).then((r) => r.data);
}

export function addProspectNote(
  id: number,
  data: CreateProspectNoteRequest,
): Promise<ProspectNoteDto> {
  return apiClient.post(`/prospects/${id}/notes`, data).then((r) => r.data);
}

export function addTeamMember(
  id: number,
  data: AddTeamMemberRequest,
): Promise<ProspectTeamMemberDto> {
  return apiClient.post(`/prospects/${id}/team-members`, data).then((r) => r.data);
}

export function removeTeamMember(id: number, memberId: number): Promise<void> {
  return apiClient.delete(`/prospects/${id}/team-members/${memberId}`).then((r) => r.data);
}

export function recalculateScore(id: number): Promise<ScoreBreakdownDto> {
  return apiClient.post(`/prospects/${id}/recalculate-score`).then((r) => r.data);
}
