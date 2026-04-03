import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  searchPartners,
  getPartnerRisk,
  getPartnerRelationships,
  getPartnerNetwork,
  searchMentorProtege,
  getGapAnalysis,
} from '@/api/teaming';
import type { PartnerSearchParams, MentorProtegeSearchParams } from '@/types/teaming';

export function usePartnerSearch(params: PartnerSearchParams) {
  return useQuery({
    queryKey: queryKeys.teaming.partners(params as Record<string, unknown>),
    queryFn: () => searchPartners(params),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function usePartnerRisk(uei: string) {
  return useQuery({
    queryKey: queryKeys.teaming.partnerRisk(uei),
    queryFn: () => getPartnerRisk(uei),
    staleTime: 5 * 60 * 1000,
    enabled: !!uei,
  });
}

export function usePartnerRelationships(uei: string, page?: number, pageSize?: number) {
  return useQuery({
    queryKey: queryKeys.teaming.relationships(uei, page),
    queryFn: () => getPartnerRelationships(uei, page, pageSize),
    staleTime: 5 * 60 * 1000,
    enabled: !!uei,
  });
}

export function usePartnerNetwork(uei: string, depth?: number) {
  return useQuery({
    queryKey: queryKeys.teaming.network(uei, depth),
    queryFn: () => getPartnerNetwork(uei, depth),
    staleTime: 5 * 60 * 1000,
    enabled: !!uei,
  });
}

export function useMentorProtege(params: MentorProtegeSearchParams) {
  return useQuery({
    queryKey: queryKeys.teaming.mentorProtege(params as Record<string, unknown>),
    queryFn: () => searchMentorProtege(params),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function useGapAnalysis(naicsCode?: string) {
  return useQuery({
    queryKey: queryKeys.teaming.gapAnalysis(naicsCode),
    queryFn: () => getGapAnalysis(naicsCode),
    staleTime: 5 * 60 * 1000,
  });
}
