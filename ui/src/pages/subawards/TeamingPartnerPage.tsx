import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import type { GridColDef, GridPaginationModel, GridSortModel } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Link from '@mui/material/Link';
import { PageHeader } from '@/components/shared/PageHeader';
import { SearchFilters } from '@/components/shared/SearchFilters';
import type { FilterConfig } from '@/components/shared/SearchFilters';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { searchTeamingPartners } from '@/api/subawards';
import { queryKeys } from '@/queries/queryKeys';
import { useResponsiveColumns } from '@/hooks/useResponsiveColumns';
import type { ResponsiveColumnConfig } from '@/hooks/useResponsiveColumns';
import type { TeamingPartnerDto, TeamingPartnerSearchParams } from '@/types/api';

const FILTER_CONFIGS: FilterConfig[] = [
  { key: 'primeUei', label: 'Primary Contractor UEI', type: 'text' },
  { key: 'naics', label: 'NAICS Code', type: 'text' },
  { key: 'minSubawards', label: 'Minimum Subaward Count', type: 'text' },
];

const formatCurrency = (value: number | null | undefined): string => {
  if (value == null) return '';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
};

function buildColumns(navigate: ReturnType<typeof useNavigate>): GridColDef<TeamingPartnerDto>[] {
  return [
    {
      field: 'primeName',
      headerName: 'Prime Contractor Name',
      flex: 1.5,
      minWidth: 200,
      renderCell: (params) => {
        const uei = params.row.primeUei;
        if (!uei) return params.value ?? '';
        return (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/entities/${encodeURIComponent(uei)}`);
            }}
          >
            {params.value ?? uei}
          </Link>
        );
      },
    },
    { field: 'primeUei', headerName: 'Prime UEI', width: 150 },
    {
      field: 'subCount',
      headerName: 'Subaward Count',
      width: 130,
      align: 'right',
      headerAlign: 'right',
    },
    {
      field: 'totalSubAmount',
      headerName: 'Total Sub Amount',
      width: 160,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value),
    },
    {
      field: 'uniqueSubs',
      headerName: 'Unique Subs',
      width: 120,
      align: 'right',
      headerAlign: 'right',
    },
    {
      field: 'naicsCodes',
      headerName: 'NAICS Codes',
      flex: 1,
      minWidth: 150,
    },
  ];
}

function parseSearchParams(sp: URLSearchParams): Record<string, unknown> {
  const vals: Record<string, unknown> = {};
  for (const key of ['primeUei', 'naics', 'minSubawards']) {
    const v = sp.get(key);
    if (v) vals[key] = v;
  }
  return vals;
}

function filtersToApiParams(
  values: Record<string, unknown>,
  paginationModel: GridPaginationModel,
  sortModel: GridSortModel,
): TeamingPartnerSearchParams {
  const params: TeamingPartnerSearchParams = {
    page: paginationModel.page + 1,
    pageSize: paginationModel.pageSize,
  };

  if (values.primeUei) params.primeUei = values.primeUei as string;
  if (values.naics) params.naics = values.naics as string;
  if (values.minSubawards) params.minSubawards = Number(values.minSubawards);

  if (sortModel.length > 0) {
    params.sortBy = sortModel[0].field;
    params.sortDescending = sortModel[0].sort === 'desc';
  }

  return params;
}

function filtersToSearchParams(values: Record<string, unknown>): Record<string, string> {
  const sp: Record<string, string> = {};
  for (const key of ['primeUei', 'naics', 'minSubawards']) {
    const v = values[key];
    if (v && typeof v === 'string' && v.length > 0) sp[key] = v;
  }
  return sp;
}

const RESPONSIVE_COLUMNS: ResponsiveColumnConfig = {
  primeUei: 'md',
  uniqueSubs: 'md',
  naicsCodes: 'lg',
};

export default function TeamingPartnerPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const columnVisibility = useResponsiveColumns(RESPONSIVE_COLUMNS);

  const committedValues = useMemo(() => parseSearchParams(searchParams), [searchParams]);
  const [editingValues, setEditingValues] = useState(committedValues);

  useEffect(() => {
    setEditingValues(committedValues);
  }, [committedValues]);

  const paginationModel: GridPaginationModel = useMemo(
    () => ({
      page: Number(searchParams.get('page') ?? 0),
      pageSize: Number(searchParams.get('pageSize') ?? 25),
    }),
    [searchParams],
  );

  const sortModel: GridSortModel = useMemo(() => {
    const sortBy = searchParams.get('sortBy');
    const sortDesc = searchParams.get('sortDescending');
    if (!sortBy) return [];
    return [{ field: sortBy, sort: sortDesc === 'true' ? 'desc' : 'asc' }];
  }, [searchParams]);

  const apiParams = useMemo(
    () => filtersToApiParams(committedValues, paginationModel, sortModel),
    [committedValues, paginationModel, sortModel],
  );

  const hasFilters = Object.keys(committedValues).length > 0;

  const { data, isLoading, isFetching, isError, refetch } = useQuery({
    queryKey: queryKeys.subawards.teamingPartners(apiParams as unknown as Record<string, unknown>),
    queryFn: () => searchTeamingPartners(apiParams),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60 * 1000,
    enabled: hasFilters,
  });

  const columns = useMemo(() => buildColumns(navigate), [navigate]);

  const handleFilterChange = useCallback(
    (key: string, value: unknown) => {
      setEditingValues((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const handleSearch = useCallback(() => {
    setSearchParams(
      { ...filtersToSearchParams(editingValues), page: '0', pageSize: String(paginationModel.pageSize) },
      { replace: true },
    );
  }, [editingValues, paginationModel.pageSize, setSearchParams]);

  const handleClear = useCallback(() => {
    setEditingValues({});
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  const handlePaginationChange = useCallback(
    (model: GridPaginationModel) => {
      const sp = filtersToSearchParams(committedValues);
      sp.page = String(model.page);
      sp.pageSize = String(model.pageSize);
      if (sortModel.length > 0) {
        sp.sortBy = sortModel[0].field;
        sp.sortDescending = String(sortModel[0].sort === 'desc');
      }
      setSearchParams(sp, { replace: true });
    },
    [committedValues, sortModel, setSearchParams],
  );

  const handleSortChange = useCallback(
    (model: GridSortModel) => {
      const sp = filtersToSearchParams(committedValues);
      sp.page = String(paginationModel.page);
      sp.pageSize = String(paginationModel.pageSize);
      if (model.length > 0) {
        sp.sortBy = model[0].field;
        sp.sortDescending = String(model[0].sort === 'desc');
      }
      setSearchParams(sp, { replace: true });
    },
    [committedValues, paginationModel, setSearchParams],
  );

  return (
    <Box>
      <PageHeader
        title="Teaming Partner Search"
        subtitle="Find prime contractors with active subcontracting relationships for teaming opportunities."
      />

      <SearchFilters
        filters={FILTER_CONFIGS}
        values={editingValues}
        onChange={handleFilterChange}
        onClear={handleClear}
        onSearch={handleSearch}
      />

      {isError && (
        <ErrorState
          title="Failed to load teaming partners"
          message="Could not retrieve teaming partner data. Please check your filters and try again."
          onRetry={() => refetch()}
        />
      )}

      {!isError && (
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          loading={isLoading || isFetching}
          rowCount={data?.totalCount ?? 0}
          paginationModel={paginationModel}
          onPaginationModelChange={handlePaginationChange}
          sortModel={sortModel}
          onSortModelChange={handleSortChange}
          getRowId={(row: TeamingPartnerDto) => row.primeUei ?? `${row.primeName}-${row.subCount}`}
          columnVisibilityModel={columnVisibility}
        />
      )}
    </Box>
  );
}
