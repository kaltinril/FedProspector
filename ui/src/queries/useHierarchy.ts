import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  searchOrganizations,
  getOrganizationDetail,
  getOrganizationChildren,
  getHierarchyTree,
  getOrganizationOpportunities,
  triggerRefresh,
  getRefreshStatus,
  lookupOrganization,
} from '@/api/hierarchy';
import type { FederalOrgSearchParams, HierarchyRefreshRequest } from '@/types/api';

export function useHierarchySearch(params: FederalOrgSearchParams) {
  return useQuery({
    queryKey: queryKeys.hierarchy.list(params as Record<string, unknown>),
    queryFn: () => searchOrganizations(params),
    staleTime: 3 * 60 * 1000,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });
}

export function useHierarchyDetail(fhOrgId: string) {
  return useQuery({
    queryKey: queryKeys.hierarchy.detail(fhOrgId),
    queryFn: () => getOrganizationDetail(fhOrgId),
    staleTime: 5 * 60 * 1000,
    enabled: !!fhOrgId,
  });
}

export function useHierarchyChildren(fhOrgId: string, enabled = true, status?: string, keyword?: string) {
  return useQuery({
    queryKey: queryKeys.hierarchy.children(fhOrgId, status, keyword),
    queryFn: () => getOrganizationChildren(fhOrgId, status, keyword),
    staleTime: 5 * 60 * 1000,
    enabled: !!fhOrgId && enabled,
  });
}

export function useHierarchyTree(keyword?: string) {
  return useQuery({
    queryKey: queryKeys.hierarchy.tree(keyword),
    queryFn: () => getHierarchyTree(keyword),
    staleTime: 10 * 60 * 1000,
  });
}

export function useHierarchyOpportunities(
  fhOrgId: string,
  pagination?: { page?: number; pageSize?: number; sortBy?: string; sortDescending?: boolean; active?: string; type?: string; setAsideCode?: string },
) {
  return useQuery({
    queryKey: queryKeys.hierarchy.opportunities(fhOrgId, pagination as Record<string, unknown>),
    queryFn: () => getOrganizationOpportunities(fhOrgId, pagination),
    staleTime: 3 * 60 * 1000,
    enabled: !!fhOrgId,
    placeholderData: (prev) => prev,
  });
}

export function useOrgLookup(name: string | undefined, agencyCode?: string) {
  const query = useQuery({
    queryKey: queryKeys.hierarchy.lookup(name, agencyCode),
    queryFn: () => lookupOrganization({ name: name!, agencyCode }),
    staleTime: 30 * 60 * 1000,
    enabled: !!name,
  });
  return {
    fhOrgId: query.data?.fhOrgId ?? null,
    isLoading: query.isLoading,
  };
}

export function useHierarchyRefresh() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: HierarchyRefreshRequest) => triggerRefresh(request),
    retry: 0,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.hierarchy.refreshStatus });
    },
  });
}

export function useHierarchyRefreshStatus(enabled = false) {
  return useQuery({
    queryKey: queryKeys.hierarchy.refreshStatus,
    queryFn: getRefreshStatus,
    staleTime: 10 * 1000,
    refetchInterval: enabled ? 5000 : false,
    refetchOnWindowFocus: enabled,
  });
}
