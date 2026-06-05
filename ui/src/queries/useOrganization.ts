import {
  useQuery,
  useQueries,
  useMutation,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  getOrganization,
  updateOrganization,
  getMembers,
  getInvites,
  createInvite,
  createUser,
  revokeInvite,
  getProfile,
  updateProfile,
  getNaics,
  setNaics,
  getCertifications,
  setCertifications,
  getPastPerformance,
  createPastPerformance,
  deletePastPerformance,
  searchNaics,
  getNaicsDetail,
  getCertificationTypes,
  getLinkedEntities,
  updateEntityLink,
  getAffiliatedSizeEligibility,
  getNaicsSectors,
  getNaicsChildren,
  getNaicsAncestors,
  getAssociatedNaics,
  addAssociatedNaics,
  deleteAssociatedNaics,
} from '@/api/organization';
import type {
  UpdateOrganizationRequest,
  CreateInviteRequest,
  CreateUserRequest,
  UpdateOrgProfileRequest,
  OrgNaicsDto,
  OrgCertificationDto,
  CreatePastPerformanceRequest,
  AffiliatedSizeEligibilityResultDto,
  UpdateEntityLinkRequest,
  CreateAssociatedNaicsRequest,
} from '@/types/organization';

// Organization details
export function useOrganization() {
  return useQuery({
    queryKey: queryKeys.organization.details,
    queryFn: getOrganization,
    staleTime: 10 * 60 * 1000, // 10 minutes — org data changes infrequently
  });
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateOrganizationRequest) => updateOrganization(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.all });
    },
  });
}

// Members
export function useOrgMembers() {
  return useQuery({
    queryKey: queryKeys.organization.members,
    queryFn: getMembers,
    staleTime: 2 * 60 * 1000,
  });
}

// Invites
export function useOrgInvites() {
  return useQuery({
    queryKey: queryKeys.organization.invites,
    queryFn: getInvites,
    staleTime: 2 * 60 * 1000,
  });
}

export function useCreateInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateInviteRequest) => createInvite(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.invites });
    },
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateUserRequest) => createUser(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.members });
    },
  });
}

export function useRevokeInvite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => revokeInvite(id),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.invites });
    },
  });
}

// Profile
export function useOrgProfile() {
  return useQuery({
    queryKey: queryKeys.organization.profile,
    queryFn: getProfile,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useUpdateOrgProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateOrgProfileRequest) => updateProfile(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.profile });
    },
  });
}

// NAICS
export function useOrgNaics() {
  return useQuery({
    queryKey: queryKeys.organization.naics,
    queryFn: getNaics,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useSetOrgNaics() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: OrgNaicsDto[]) => setNaics(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.naics });
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.profile });
    },
  });
}

// Associated NAICS (Phase 136 Unit G)
export function useAssociatedNaics() {
  return useQuery({
    queryKey: queryKeys.organization.associatedNaics,
    queryFn: getAssociatedNaics,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useAddAssociatedNaics() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateAssociatedNaicsRequest) => addAssociatedNaics(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.associatedNaics });
    },
  });
}

export function useDeleteAssociatedNaics() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteAssociatedNaics(id),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.associatedNaics });
    },
  });
}

// Certifications
export function useOrgCertifications() {
  return useQuery({
    queryKey: queryKeys.organization.certifications,
    queryFn: getCertifications,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useSetOrgCertifications() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: OrgCertificationDto[]) => setCertifications(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.certifications });
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.profile });
    },
  });
}

// Past performance
export function useOrgPastPerformance() {
  return useQuery({
    queryKey: queryKeys.organization.pastPerformance,
    queryFn: getPastPerformance,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

export function useCreatePastPerformance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreatePastPerformanceRequest) => createPastPerformance(data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.pastPerformance });
    },
  });
}

export function useDeletePastPerformance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deletePastPerformance(id),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.pastPerformance });
    },
  });
}

// Linked entities
export function useOrgEntities() {
  return useQuery({
    queryKey: queryKeys.organization.entities,
    queryFn: getLinkedEntities,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Phase 136 Unit F: edit an existing linked entity (affiliate revenue/employees, etc.) anytime.
export function useUpdateEntityLink() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ linkId, data }: { linkId: number; data: UpdateEntityLinkRequest }) =>
      updateEntityLink(linkId, data),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.entities });
      // Affiliate figures feed the affiliation size roll-up.
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.all });
    },
  });
}

// Phase 133 Task 6: affiliation-aware size determination for a single NAICS code.
export function useAffiliatedSizeEligibility(naicsCode: string | null | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.organization.sizeEligibility(naicsCode ?? ''),
    queryFn: () => getAffiliatedSizeEligibility(naicsCode as string),
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: enabled && !!naicsCode,
  });
}

/**
 * Phase 133 Task 6: affiliation-aware size determination across MANY NAICS codes at once.
 *
 * Fires one `GET /org/size-eligibility/{naicsCode}` per code via `useQueries`, reusing the same
 * cache key and staleTime as the single-code hook, so a code shown by both a monitor card and
 * the flip banner is fetched once. A typical org registers only a handful of NAICS, so the
 * fan-out is small; if an org ever carried dozens this would warrant a batch endpoint, but that
 * is a C# change out of scope here.
 *
 * Returns the raw `useQueries` array of `UseQueryResult` so callers aggregate loading/error and
 * filter the verdicts. Codes are expected to be de-duplicated by the caller.
 */
export function useAffiliatedSizeEligibilityForCodes(
  naicsCodes: string[],
  enabled = true,
): UseQueryResult<AffiliatedSizeEligibilityResultDto>[] {
  return useQueries({
    queries: naicsCodes.map((code) => ({
      queryKey: queryKeys.organization.sizeEligibility(code),
      queryFn: () => getAffiliatedSizeEligibility(code),
      staleTime: 5 * 60 * 1000, // 5 minutes — matches useAffiliatedSizeEligibility
      enabled: enabled && !!code,
    })),
  });
}

// Reference data
export function useNaicsSearch(query: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.reference.naics(query),
    queryFn: () => searchNaics(query),
    staleTime: 30 * 60 * 1000, // 30 minutes — reference data
    enabled: enabled && query.length >= 2,
  });
}

export function useNaicsDetail(code: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.reference.naicsDetail(code),
    queryFn: () => getNaicsDetail(code),
    staleTime: 30 * 60 * 1000, // 30 minutes — reference data
    enabled,
  });
}

export function useCertificationTypes() {
  return useQuery({
    queryKey: queryKeys.reference.certificationTypes,
    queryFn: getCertificationTypes,
    staleTime: 30 * 60 * 1000,
  });
}

// --- Phase 129 NAICS hierarchy (Unit E) ---

/** Top-level 2-digit NAICS sectors (root of the browser tree). */
export function useNaicsSectors() {
  return useQuery({
    queryKey: queryKeys.reference.naicsSectors,
    queryFn: getNaicsSectors,
    staleTime: 30 * 60 * 1000, // 30 minutes — reference data rarely changes
  });
}

/** Immediate children of a NAICS code, fetched lazily when a node expands. */
export function useNaicsChildren(code: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.reference.naicsChildren(code),
    queryFn: () => getNaicsChildren(code),
    staleTime: 30 * 60 * 1000,
    enabled: enabled && code.length > 0,
  });
}

/** Ancestor chain (sector -> code) for breadcrumbs. */
export function useNaicsAncestors(code: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.reference.naicsAncestors(code),
    queryFn: () => getNaicsAncestors(code),
    staleTime: 30 * 60 * 1000,
    enabled: enabled && code.length > 0,
  });
}
