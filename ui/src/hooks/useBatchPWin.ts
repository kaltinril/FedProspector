import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchBatchPWin } from '@/api/opportunities';
import { queryKeys } from '@/queries/queryKeys';
import type { BatchPWinEntry } from '@/types/api';

/**
 * Fetches pWin scores in batch for the given noticeIds (typically one page of
 * grid rows). Returns a Map for O(1) lookups.
 */
export function useBatchPWin(noticeIds: string[]) {
  // Sort for stable query key regardless of row order
  const sortedIds = useMemo(() => [...noticeIds].sort(), [noticeIds]);

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.opportunities.pwinBatch(sortedIds),
    queryFn: () => fetchBatchPWin(sortedIds),
    enabled: sortedIds.length > 0,
    staleTime: 5 * 60 * 1000,
  });

  const pwinMap = useMemo(() => {
    const map = new Map<string, BatchPWinEntry>();
    if (data?.results) {
      for (const [noticeId, entry] of Object.entries(data.results)) {
        if (entry) {
          map.set(noticeId, entry);
        }
      }
    }
    return map;
  }, [data]);

  return { pwinMap, isLoading };
}
