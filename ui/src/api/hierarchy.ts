import apiClient from './client';
import type { PagedResponse } from '@/types/common';
import type {
  FederalOrgListItem,
  FederalOrgDetail,
  FederalOrgTreeNode,
  FederalOrgSearchParams,
  OpportunitySearchResult,
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

export function triggerRefresh(request: HierarchyRefreshRequest): Promise<HierarchyRefreshStatus> {
  return apiClient.post('/hierarchy/refresh', request).then((r) => r.data);
}

export function getRefreshStatus(): Promise<HierarchyRefreshStatus> {
  return apiClient.get('/hierarchy/refresh/status').then((r) => r.data);
}

/**
 * Resolve an agency name (and optional code) to a single FederalOrgListItem.
 * Tries agencyCode first if provided, then falls back to keyword search.
 */
export async function lookupOrganization(params: {
  name: string;
  agencyCode?: string;
}): Promise<FederalOrgListItem | null> {
  if (params.agencyCode) {
    const result = await searchOrganizations({
      agencyCode: params.agencyCode,
      pageSize: 1,
    });
    if (result.items.length > 0) return result.items[0];
  }
  const result = await searchOrganizations({
    keyword: params.name,
    pageSize: 1,
  });
  return result.items.length > 0 ? result.items[0] : null;
}
