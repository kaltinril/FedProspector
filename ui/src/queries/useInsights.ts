import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import {
  getSimilarOpportunities,
  getDataQualityDashboard,
  getProspectCompetitorSummary,
} from '@/api/insights';

export function useSimilarOpportunities(noticeId: string, maxResults = 20, enabled = true) {
  return useQuery({
    queryKey: queryKeys.insights.similar(noticeId, maxResults),
    queryFn: () => getSimilarOpportunities(noticeId, maxResults),
    staleTime: 5 * 60 * 1000,
    enabled: enabled && !!noticeId,
  });
}

export function useDataQualityDashboard(enabled = true) {
  return useQuery({
    queryKey: queryKeys.insights.dataQuality,
    queryFn: () => getDataQualityDashboard(),
    staleTime: 60 * 1000,
    enabled,
  });
}

export function useProspectCompetitorSummary(prospectId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.insights.prospectCompetitor(prospectId),
    queryFn: () => getProspectCompetitorSummary(prospectId),
    staleTime: 5 * 60 * 1000,
    enabled: enabled && prospectId > 0,
  });
}
