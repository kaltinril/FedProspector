import axios from 'axios';
import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  EtlStatusDto,
  UserListDto,
  UpdateUserRequest,
  ResetPasswordResponse,
  CreateOrganizationRequest,
  CreateOwnerRequest,
  LoadHistoryResponse,
  LoadHistoryParams,
  HealthResponse,
} from '@/types/api';

export function getEtlStatus(): Promise<EtlStatusDto> {
  return apiClient.get('/admin/etl-status').then((r) => r.data);
}

export function listUsers(params?: {
  page?: number;
  pageSize?: number;
}): Promise<PagedResponse<UserListDto>> {
  return apiClient.get('/admin/users', { params }).then((r) => r.data);
}

export function updateUser(id: number, data: UpdateUserRequest): Promise<void> {
  return apiClient.patch(`/admin/users/${id}`, data).then((r) => r.data);
}

export function resetUserPassword(id: number): Promise<ResetPasswordResponse> {
  return apiClient.post(`/admin/users/${id}/reset-password`).then((r) => r.data);
}

export function createOrganization(data: CreateOrganizationRequest): Promise<void> {
  return apiClient.post('/admin/organizations', data).then((r) => r.data);
}

export function createOrganizationOwner(
  orgId: number,
  data: CreateOwnerRequest,
): Promise<void> {
  return apiClient.post(`/admin/organizations/${orgId}/owner`, data).then((r) => r.data);
}

export function getLoadHistory(params?: LoadHistoryParams): Promise<LoadHistoryResponse> {
  return apiClient.get('/admin/load-history', { params }).then((r) => r.data);
}

export function getHealth(): Promise<HealthResponse> {
  // /health is a top-level endpoint, not under /api/v1
  return axios.get('/health', { withCredentials: true }).then((r) => r.data);
}
