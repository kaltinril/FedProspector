import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  FederalOrgListItem,
  FederalOrgDetail,
  FederalOrgTreeNode,
  FederalOrgSearchParams,
  FederalOrgStats,
  OpportunitySearchResult,
  AwardSearchResult,
  HierarchyRefreshRequest,
  HierarchyRefreshStatus,
} from '@/types/api';

export function searchOrganizations(
  params: FederalOrgSearchParams,
): Promise<PagedResponse<FederalOrgListItem>> {
  return apiClient.get('/hierarchy', { params }).then((r) => r.data);
}

export function getOrganizationDetail(fhOrgId: string): Promise<FederalOrgDetail> {
  return apiClient.get(`/hierarchy/${encodeURIComponent(fhOrgId)}`).then((r) => r.data);
}

export function getOrganizationChildren(fhOrgId: string, status?: string, keyword?: string): Promise<FederalOrgListItem[]> {
  return apiClient.get(`/hierarchy/${encodeURIComponent(fhOrgId)}/children`, {
    params: { ...(status ? { status } : {}), ...(keyword ? { keyword } : {}) },
  }).then((r) => r.data);
}

export function getHierarchyTree(keyword?: string): Promise<FederalOrgTreeNode[]> {
  return apiClient.get('/hierarchy/tree', { params: keyword ? { keyword } : undefined }).then((r) => r.data);
}

export function getOrganizationOpportunities(
  fhOrgId: string,
  params?: { page?: number; pageSize?: number; sortBy?: string; sortDescending?: boolean; active?: string; type?: string; setAsideCode?: string },
): Promise<PagedResponse<OpportunitySearchResult>> {
  return apiClient.get(`/hierarchy/${encodeURIComponent(fhOrgId)}/opportunities`, { params }).then((r) => r.data);
}

export function getOrganizationAwards(
  fhOrgId: string,
  params?: { page?: number; pageSize?: number; sortBy?: string; sortDescending?: boolean },
): Promise<PagedResponse<AwardSearchResult>> {
  return apiClient.get(`/hierarchy/${encodeURIComponent(fhOrgId)}/awards`, { params }).then((r) => r.data);
}

export function getOrganizationStats(fhOrgId: string): Promise<FederalOrgStats> {
  return apiClient.get(`/hierarchy/${encodeURIComponent(fhOrgId)}/stats`).then((r) => r.data);
}

export function triggerRefresh(request: HierarchyRefreshRequest): Promise<HierarchyRefreshStatus> {
  return apiClient.post('/hierarchy/refresh', request).then((r) => r.data);
}

export function getRefreshStatus(): Promise<HierarchyRefreshStatus> {
  return apiClient.get('/hierarchy/refresh/status').then((r) => r.data);
}
