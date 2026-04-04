import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  getProfileCompleteness,
  importUei,
  getCertificationAlerts,
  getSizeStandardAlerts,
  getPastPerformanceRelevance,
  getPortfolioGaps,
  getPscCodes,
  addPscCode,
  deletePscCode,
} from '@/api/onboarding';

export function useProfileCompleteness() {
  return useQuery({
    queryKey: queryKeys.onboarding.profileCompleteness,
    queryFn: () => getProfileCompleteness(),
    staleTime: 60 * 1000,
  });
}

export function useImportUei() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (uei: string) => importUei(uei),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.onboarding.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.organization.all });
    },
  });
}

export function useCertificationAlerts() {
  return useQuery({
    queryKey: queryKeys.onboarding.certificationAlerts,
    queryFn: () => getCertificationAlerts(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSizeStandardAlerts() {
  return useQuery({
    queryKey: queryKeys.onboarding.sizeStandardAlerts,
    queryFn: () => getSizeStandardAlerts(),
    staleTime: 5 * 60 * 1000,
  });
}

export function usePastPerformanceRelevance(noticeId?: string) {
  return useQuery({
    queryKey: queryKeys.onboarding.pastPerformanceRelevance(noticeId),
    queryFn: () => getPastPerformanceRelevance(noticeId),
    staleTime: 5 * 60 * 1000,
  });
}

export function usePortfolioGaps() {
  return useQuery({
    queryKey: queryKeys.onboarding.portfolioGaps,
    queryFn: () => getPortfolioGaps(),
    staleTime: 5 * 60 * 1000,
  });
}

export function usePscCodes() {
  return useQuery({
    queryKey: queryKeys.onboarding.pscCodes,
    queryFn: () => getPscCodes(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useAddPscCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (pscCode: string) => addPscCode(pscCode),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.onboarding.pscCodes });
      void queryClient.invalidateQueries({ queryKey: queryKeys.onboarding.profileCompleteness });
    },
  });
}

export function useDeletePscCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deletePscCode(id),
    retry: 1,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.onboarding.pscCodes });
      void queryClient.invalidateQueries({ queryKey: queryKeys.onboarding.profileCompleteness });
    },
  });
}
