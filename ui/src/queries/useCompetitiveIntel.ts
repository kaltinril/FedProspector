import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  searchRecompeteCandidates,
  getAgencyPatterns,
  getAgencyBuyingPatterns,
  getCompetitorDossier,
  searchOffices,
  getOfficeProfile,
} from '@/api/competitiveIntel';
import type {
  RecompeteCandidateSearchParams,
  AgencyPatternSearchParams,
  OfficeSearchParams,
} from '@/types/competitiveIntel';

export function useRecompeteCandidates(params: RecompeteCandidateSearchParams) {
  return useQuery({
    queryKey: queryKeys.competitiveIntel.recompetes(params as Record<string, unknown>),
    queryFn: () => searchRecompeteCandidates(params),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useAgencyPatterns(params: AgencyPatternSearchParams) {
  return useQuery({
    queryKey: queryKeys.competitiveIntel.agencyPatterns(params as Record<string, unknown>),
    queryFn: () => getAgencyPatterns(params),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useAgencyBuyingPatterns(agencyCode: string, year?: number) {
  return useQuery({
    queryKey: queryKeys.competitiveIntel.buyingPatterns(agencyCode, year),
    queryFn: () => getAgencyBuyingPatterns(agencyCode, year),
    staleTime: 5 * 60 * 1000,
    enabled: !!agencyCode,
  });
}

export function useCompetitorDossier(uei: string) {
  return useQuery({
    queryKey: queryKeys.competitiveIntel.competitorDossier(uei),
    queryFn: () => getCompetitorDossier(uei),
    staleTime: 5 * 60 * 1000,
    enabled: !!uei,
  });
}

export function useOfficeSearch(params: OfficeSearchParams) {
  return useQuery({
    queryKey: queryKeys.competitiveIntel.offices(params as Record<string, unknown>),
    queryFn: () => searchOffices(params),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useOfficeProfile(officeCode: string) {
  return useQuery({
    queryKey: queryKeys.competitiveIntel.officeProfile(officeCode),
    queryFn: () => getOfficeProfile(officeCode),
    staleTime: 5 * 60 * 1000,
    enabled: !!officeCode,
  });
}
