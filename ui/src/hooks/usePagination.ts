import { useState, useCallback } from 'react';

export interface PaginationState {
  page: number;
  pageSize: number;
  sortBy: string;
  sortDescending: boolean;
}

export interface UsePaginationReturn extends PaginationState {
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
  setSortBy: (sortBy: string) => void;
  toggleSortDirection: () => void;
  setSortDescending: (desc: boolean) => void;
  resetPage: () => void;
}

export function usePagination(defaults?: Partial<PaginationState>): UsePaginationReturn {
  const [state, setState] = useState<PaginationState>({
    page: defaults?.page ?? 1,
    pageSize: defaults?.pageSize ?? 25,
    sortBy: defaults?.sortBy ?? '',
    sortDescending: defaults?.sortDescending ?? false,
  });

  const setPage = useCallback((page: number) => {
    setState((prev) => ({ ...prev, page }));
  }, []);

  const setPageSize = useCallback((pageSize: number) => {
    setState((prev) => ({ ...prev, pageSize, page: 1 }));
  }, []);

  const setSortBy = useCallback((sortBy: string) => {
    setState((prev) => ({ ...prev, sortBy, page: 1 }));
  }, []);

  const toggleSortDirection = useCallback(() => {
    setState((prev) => ({ ...prev, sortDescending: !prev.sortDescending, page: 1 }));
  }, []);

  const setSortDescending = useCallback((desc: boolean) => {
    setState((prev) => ({ ...prev, sortDescending: desc, page: 1 }));
  }, []);

  const resetPage = useCallback(() => {
    setState((prev) => ({ ...prev, page: 1 }));
  }, []);

  return {
    ...state,
    setPage,
    setPageSize,
    setSortBy,
    toggleSortDirection,
    setSortDescending,
    resetPage,
  };
}
