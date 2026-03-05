import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import { getDashboard } from '@/api/dashboard';

export function useDashboard() {
  return useQuery({
    queryKey: queryKeys.dashboard.all,
    queryFn: getDashboard,
    staleTime: 60 * 1000,
    refetchOnWindowFocus: true,
  });
}
