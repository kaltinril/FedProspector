import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { useSearchFilters, type SearchFilterDef } from './useSearchParams';

export function useFilteredSearch<TFilters extends SearchFilterDef, TResult>(
  queryKey: string,
  defaults: TFilters,
  fetcher: (params: TFilters) => Promise<TResult>,
) {
  const { filters, setFilter, setFilters, clearFilters } = useSearchFilters(defaults);

  const query = useQuery({
    queryKey: [queryKey, filters],
    queryFn: () => fetcher(filters),
    placeholderData: keepPreviousData,
  });

  return { filters, setFilter, setFilters, clearFilters, query };
}
