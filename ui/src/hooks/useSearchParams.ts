import { useSearchParams as useRouterSearchParams } from 'react-router-dom';
import { useCallback, useMemo } from 'react';

export interface SearchFilterDef {
  [key: string]: string | number | boolean | string[] | undefined;
}

export function useSearchFilters<T extends SearchFilterDef>(defaults: T) {
  const [searchParams, setSearchParams] = useRouterSearchParams();

  const filters = useMemo(() => {
    const result = { ...defaults } as T;
    for (const key of Object.keys(defaults)) {
      const paramValue = searchParams.get(key);
      const defaultVal = defaults[key];

      if (paramValue === null) continue;

      if (typeof defaultVal === 'number') {
        const num = Number(paramValue);
        if (!isNaN(num)) (result as Record<string, unknown>)[key] = num;
      } else if (typeof defaultVal === 'boolean') {
        (result as Record<string, unknown>)[key] = paramValue === 'true';
      } else if (Array.isArray(defaultVal)) {
        (result as Record<string, unknown>)[key] = paramValue.split(',').filter(Boolean);
      } else {
        (result as Record<string, unknown>)[key] = paramValue;
      }
    }
    return result;
  }, [searchParams, defaults]);

  const setFilter = useCallback(
    (key: keyof T, value: T[keyof T]) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (
            value === undefined ||
            value === '' ||
            (Array.isArray(value) && value.length === 0)
          ) {
            next.delete(String(key));
          } else if (Array.isArray(value)) {
            next.set(String(key), value.join(','));
          } else {
            next.set(String(key), String(value));
          }
          // Reset to page 1 when filters change (unless changing page itself)
          if (key !== 'page') next.set('page', '1');
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const setFilters = useCallback(
    (updates: Partial<T>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(updates)) {
            if (
              value === undefined ||
              value === '' ||
              (Array.isArray(value) && value.length === 0)
            ) {
              next.delete(key);
            } else if (Array.isArray(value)) {
              next.set(key, value.join(','));
            } else {
              next.set(key, String(value));
            }
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const clearFilters = useCallback(() => {
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  return { filters, setFilter, setFilters, clearFilters };
}
