import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  getOrganization,
  updateOrganization,
  getMembers,
  getInvites,
  createInvite,
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
} from '@/api/organization';
import type {
  UpdateOrganizationRequest,
  CreateInviteRequest,
  UpdateOrgProfileRequest,
  OrgNaicsDto,
  OrgCertificationDto,
  CreatePastPerformanceRequest,
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
