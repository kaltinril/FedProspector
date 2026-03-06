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
import { searchAwards } from '@/api/awards';
import { queryKeys } from '@/queries/queryKeys';
import type { AwardSearchResult, AwardSearchParams } from '@/types/api';

const SET_ASIDE_OPTIONS = [
  { value: 'SBA', label: 'Small Business' },
  { value: 'SBP', label: 'Small Business Set-Aside' },
  { value: '8A', label: '8(a)' },
  { value: '8AN', label: '8(a) Sole Source' },
  { value: 'WOSB', label: 'WOSB' },
  { value: 'EDWOSB', label: 'EDWOSB' },
  { value: 'HZC', label: 'HUBZone' },
  { value: 'SDVOSBC', label: 'SDVOSB' },
];

const FILTER_CONFIGS: FilterConfig[] = [
  { key: 'solicitation', label: 'Solicitation Number', type: 'text' },
  { key: 'naics', label: 'NAICS Code', type: 'text' },
  { key: 'agency', label: 'Agency', type: 'text' },
  { key: 'vendorSearch', label: 'Vendor UEI or Name', type: 'text' },
  { key: 'setAside', label: 'Set-Aside Type', type: 'select', options: SET_ASIDE_OPTIONS },
  { key: 'minValue', label: 'Award Value Min', type: 'text' },
  { key: 'maxValue', label: 'Award Value Max', type: 'text' },
  { key: 'dateRange', label: 'Date Signed', type: 'dateRange' },
];

const formatCurrency = (value: number | null | undefined): string => {
  if (value == null) return '';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value);
};

function buildColumns(navigate: ReturnType<typeof useNavigate>): GridColDef<AwardSearchResult>[] {
  return [
    {
      field: 'contractId',
      headerName: 'Contract ID',
      flex: 1.2,
      minWidth: 160,
      renderCell: (params) => (
        <Link
          component="button"
          variant="body2"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/awards/${encodeURIComponent(params.value)}`);
          }}
        >
          {params.value}
        </Link>
      ),
    },
    { field: 'vendorName', headerName: 'Vendor Name', flex: 1.2, minWidth: 150 },
    { field: 'agencyName', headerName: 'Agency', flex: 1, minWidth: 140 },
    { field: 'naicsCode', headerName: 'NAICS', width: 100 },
    { field: 'setAsideType', headerName: 'Set-Aside', width: 120 },
    {
      field: 'dateSigned',
      headerName: 'Date Signed',
      width: 120,
      valueFormatter: (value: string | null | undefined) =>
        value ? new Date(value).toLocaleDateString() : '',
    },
    {
      field: 'baseAndAllOptions',
      headerName: 'Total Value',
      width: 140,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value),
    },
    { field: 'typeOfContract', headerName: 'Contract Type', width: 120 },
  ];
}

function parseSearchParams(sp: URLSearchParams): Record<string, unknown> {
  const vals: Record<string, unknown> = {};
  for (const key of ['solicitation', 'naics', 'agency', 'vendorSearch', 'setAside', 'minValue', 'maxValue']) {
    const v = sp.get(key);
    if (v) vals[key] = v;
  }
  const dateFrom = sp.get('dateFrom');
  const dateTo = sp.get('dateTo');
  if (dateFrom || dateTo) {
    vals.dateRange = { start: dateFrom ?? '', end: dateTo ?? '' };
  }
  return vals;
}

function filtersToApiParams(
  values: Record<string, unknown>,
  paginationModel: GridPaginationModel,
  sortModel: GridSortModel,
): AwardSearchParams {
  const params: AwardSearchParams = {
    page: paginationModel.page + 1,
    pageSize: paginationModel.pageSize,
  };

  const vendorSearch = values.vendorSearch as string | undefined;
  if (vendorSearch) {
    // If it looks like a UEI (alphanumeric, 12 chars), search by UEI; otherwise by name
    if (/^[A-Z0-9]{12}$/i.test(vendorSearch.trim())) {
      params.vendorUei = vendorSearch.trim();
    } else {
      params.vendorName = vendorSearch.trim();
    }
  }

  if (values.solicitation) params.solicitation = values.solicitation as string;
  if (values.naics) params.naics = values.naics as string;
  if (values.agency) params.agency = values.agency as string;
  if (values.setAside) params.setAside = values.setAside as string;
  if (values.minValue) params.minValue = Number(values.minValue);
  if (values.maxValue) params.maxValue = Number(values.maxValue);

  const dateRange = values.dateRange as { start?: string; end?: string } | undefined;
  if (dateRange?.start) params.dateFrom = dateRange.start;
  if (dateRange?.end) params.dateTo = dateRange.end;

  if (sortModel.length > 0) {
    params.sortBy = sortModel[0].field;
    params.sortDescending = sortModel[0].sort === 'desc';
  }

  return params;
}

function filtersToSearchParams(values: Record<string, unknown>): Record<string, string> {
  const sp: Record<string, string> = {};
  for (const key of ['solicitation', 'naics', 'agency', 'vendorSearch', 'setAside', 'minValue', 'maxValue']) {
    const v = values[key];
    if (v && typeof v === 'string' && v.length > 0) sp[key] = v;
  }
  const dateRange = values.dateRange as { start?: string; end?: string } | undefined;
  if (dateRange?.start) sp.dateFrom = dateRange.start;
  if (dateRange?.end) sp.dateTo = dateRange.end;
  return sp;
}

export default function AwardSearchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const committedValues = useMemo(() => parseSearchParams(searchParams), [searchParams]);

  const [editingValues, setEditingValues] = useState<Record<string, unknown>>(committedValues);

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
    queryKey: queryKeys.awards.list(apiParams as unknown as Record<string, unknown>),
    queryFn: () => searchAwards(apiParams),
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
        title="Award Search"
        subtitle="Search federal contract awards by solicitation, agency, vendor, or NAICS code."
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
          title="Failed to load awards"
          message="Could not retrieve award data. Please check your filters and try again."
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
          getRowId={(row: AwardSearchResult) => row.contractId}
        />
      )}
    </Box>
  );
}
