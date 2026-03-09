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
import { StatusChip } from '@/components/shared/StatusChip';
import { searchEntities } from '@/api/entities';
import { queryKeys } from '@/queries/queryKeys';
import { useResponsiveColumns } from '@/hooks/useResponsiveColumns';
import type { ResponsiveColumnConfig } from '@/hooks/useResponsiveColumns';
import type { EntitySearchResult, EntitySearchParams } from '@/types/api';

const SBA_CERTIFICATION_OPTIONS = [
  { value: 'WOSB', label: 'WOSB' },
  { value: 'EDWOSB', label: 'EDWOSB' },
  { value: '8(a)', label: '8(a)' },
  { value: 'HUBZone', label: 'HUBZone' },
  { value: 'SDVOSB', label: 'SDVOSB' },
];

const REGISTRATION_STATUS_OPTIONS = [
  { value: 'Active', label: 'Active' },
  { value: 'Expired', label: 'Expired' },
  { value: '', label: 'All' },
];

const FILTER_CONFIGS: FilterConfig[] = [
  { key: 'name', label: 'Company Name', type: 'text' },
  { key: 'uei', label: 'UEI', type: 'text' },
  { key: 'naics', label: 'NAICS Code', type: 'text' },
  { key: 'state', label: 'State', type: 'text' },
  { key: 'businessType', label: 'Business Type', type: 'text' },
  { key: 'sbaCertification', label: 'SBA Certification', type: 'select', options: SBA_CERTIFICATION_OPTIONS },
  { key: 'registrationStatus', label: 'Registration Status', type: 'select', options: REGISTRATION_STATUS_OPTIONS },
];

function buildColumns(navigate: ReturnType<typeof useNavigate>): GridColDef<EntitySearchResult>[] {
  return [
    {
      field: 'legalBusinessName',
      headerName: 'Legal Business Name',
      flex: 1.5,
      minWidth: 200,
      renderCell: (params) => (
        <Link
          component="button"
          variant="body2"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/entities/${encodeURIComponent(params.row.ueiSam)}`);
          }}
        >
          {params.value}
        </Link>
      ),
    },
    { field: 'dbaName', headerName: 'DBA Name', flex: 1, minWidth: 150 },
    { field: 'ueiSam', headerName: 'UEI', width: 140 },
    { field: 'primaryNaics', headerName: 'Primary NAICS', width: 120 },
    {
      field: 'registrationStatus',
      headerName: 'Registration Status',
      width: 150,
      renderCell: (params) =>
        params.value ? <StatusChip status={params.value} /> : null,
    },
    { field: 'popState', headerName: 'State', width: 80 },
    {
      field: 'entityUrl',
      headerName: 'Entity URL',
      flex: 1,
      minWidth: 120,
      renderCell: (params) =>
        params.value ? (
          <Link
            href={params.value}
            target="_blank"
            rel="noopener noreferrer"
            variant="body2"
            onClick={(e) => e.stopPropagation()}
          >
            Visit Site
          </Link>
        ) : null,
    },
  ];
}

function parseSearchParams(sp: URLSearchParams): Record<string, unknown> {
  const vals: Record<string, unknown> = {};
  for (const key of ['name', 'uei', 'naics', 'state', 'businessType', 'sbaCertification', 'registrationStatus']) {
    const v = sp.get(key);
    if (v) vals[key] = v;
  }
  return vals;
}

function filtersToApiParams(
  values: Record<string, unknown>,
  paginationModel: GridPaginationModel,
  sortModel: GridSortModel,
): EntitySearchParams {
  const params: EntitySearchParams = {
    page: paginationModel.page + 1,
    pageSize: paginationModel.pageSize,
  };

  if (values.name) params.name = values.name as string;
  if (values.uei) params.uei = values.uei as string;
  if (values.naics) params.naics = values.naics as string;
  if (values.state) params.state = values.state as string;
  if (values.businessType) params.businessType = values.businessType as string;
  if (values.sbaCertification) params.sbaCertification = values.sbaCertification as string;
  if (values.registrationStatus) params.registrationStatus = values.registrationStatus as string;

  if (sortModel.length > 0) {
    params.sortBy = sortModel[0].field;
    params.sortDescending = sortModel[0].sort === 'desc';
  }

  return params;
}

function filtersToSearchParams(values: Record<string, unknown>): Record<string, string> {
  const sp: Record<string, string> = {};
  for (const key of ['name', 'uei', 'naics', 'state', 'businessType', 'sbaCertification', 'registrationStatus']) {
    const v = values[key];
    if (v && typeof v === 'string' && v.length > 0) sp[key] = v;
  }
  return sp;
}

const RESPONSIVE_COLUMNS: ResponsiveColumnConfig = {
  dbaName: 'md',
  primaryNaics: 'md',
  popState: 'lg',
  entityUrl: 'lg',
};

export default function EntitySearchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const columnVisibility = useResponsiveColumns(RESPONSIVE_COLUMNS);

  // Committed filter values (from URL — these drive the API query)
  const committedValues = useMemo(() => parseSearchParams(searchParams), [searchParams]);

  // Local editing state (tracks what the user is typing before hitting Search)
  const [editingValues, setEditingValues] = useState<Record<string, unknown>>(committedValues);

  // Sync editing state when URL params change externally (e.g., browser back/forward)
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
    queryKey: queryKeys.entities.list(apiParams as unknown as Record<string, unknown>),
    queryFn: () => searchEntities(apiParams),
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
        title="Entity Search"
        subtitle="Search SAM.gov registered entities by name, UEI, NAICS, or SBA certification."
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
          title="Failed to load entities"
          message="Could not retrieve entity data. Please check your filters and try again."
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
          getRowId={(row: EntitySearchResult) => row.ueiSam}
          columnVisibilityModel={columnVisibility}
        />
      )}
    </Box>
  );
}
