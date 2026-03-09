import { useQuery } from '@tanstack/react-query';
import { queryKeys } from './queryKeys';
import { getDashboard } from '@/api/dashboard';

export function useDashboard() {
  return useQuery({
    queryKey: queryKeys.dashboard.all,
    queryFn: getDashboard,
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchOnWindowFocus: true,
    refetchInterval: 5 * 60 * 1000,
    refetchIntervalInBackground: false,
  });
}
