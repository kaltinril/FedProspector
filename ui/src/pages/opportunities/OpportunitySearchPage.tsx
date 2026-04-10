import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, keepPreviousData } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import type { GridColDef, GridPaginationModel, GridSortModel, GridRowParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import FormControlLabel from '@mui/material/FormControlLabel';
import IconButton from '@mui/material/IconButton';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';
import DownloadIcon from '@mui/icons-material/Download';
import BookmarkAddIcon from '@mui/icons-material/BookmarkAdd';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import VisibilityIcon from '@mui/icons-material/Visibility';

import { PageHeader } from '@/components/shared/PageHeader';
import { SearchFilters } from '@/components/shared/SearchFilters';
import type { FilterConfig } from '@/components/shared/SearchFilters';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { CurrencyDisplay } from '@/components/shared/CurrencyDisplay';
import { AgencyLink } from '@/components/shared/AgencyLink';
import { searchOpportunities, exportOpportunities } from '@/api/opportunities';
import { createProspect } from '@/api/prospects';
import { queryKeys } from '@/queries/queryKeys';
import { useIgnoreOpportunity, useUnignoreOpportunity, useIgnoredOpportunityIds } from '@/queries/useOpportunities';
import { useResponsiveColumns } from '@/hooks/useResponsiveColumns';
import type { ResponsiveColumnConfig } from '@/hooks/useResponsiveColumns';
import type { OpportunitySearchResult, OpportunitySearchParams } from '@/types/api';
import { getSetAsideChipProps } from '@/utils/constants';
import { OPPORTUNITY_SET_ASIDE_OPTIONS } from '@/constants/options';

// ---------------------------------------------------------------------------
// Filter configuration
// ---------------------------------------------------------------------------

const OPEN_ONLY_OPTIONS = [
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
  { value: 'all', label: 'All' },
];

const FILTER_CONFIGS: FilterConfig[] = [
  { key: 'keyword', label: 'Keyword', type: 'text' },
  { key: 'solicitation', label: 'Solicitation #', type: 'text' },
  { key: 'naics', label: 'NAICS Code', type: 'text' },
  { key: 'setAside', label: 'Set-Aside', type: 'select', options: OPPORTUNITY_SET_ASIDE_OPTIONS },
  { key: 'department', label: 'Department', type: 'text' },
  { key: 'state', label: 'State (POP)', type: 'text' },
  { key: 'daysOut', label: 'Days Out', type: 'text' },
  { key: 'openOnly', label: 'Open Only', type: 'select', options: OPEN_ONLY_OPTIONS },
];

// ---------------------------------------------------------------------------
// URL <-> filter helpers
// ---------------------------------------------------------------------------

const FILTER_KEYS = ['keyword', 'solicitation', 'naics', 'setAside', 'department', 'state', 'daysOut', 'openOnly'] as const;

function readFiltersFromParams(params: URLSearchParams): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  for (const key of FILTER_KEYS) {
    const v = params.get(key);
    if (v != null && v !== '') {
      values[key] = v;
    }
  }
  // Default openOnly to "yes" if not in URL
  if (!values.openOnly) {
    values.openOnly = 'yes';
  }
  return values;
}

function writeFiltersToParams(values: Record<string, unknown>): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const v = values[key];
    if (v != null && v !== '' && v !== 'yes') {
      // Skip openOnly=yes since it's the default
      params.set(key, String(v));
    } else if (key !== 'openOnly' && v != null && v !== '') {
      params.set(key, String(v));
    }
  }
  return params;
}

function filtersToApiParams(
  values: Record<string, unknown>,
  pagination: GridPaginationModel,
  sortModel: GridSortModel,
): OpportunitySearchParams {
  const params: OpportunitySearchParams = {
    page: pagination.page + 1, // MUI 0-indexed -> API 1-indexed
    pageSize: pagination.pageSize,
  };

  if (values.keyword) params.keyword = String(values.keyword);
  if (values.solicitation) params.solicitation = String(values.solicitation);
  if (values.naics) params.naics = String(values.naics);
  if (values.setAside) params.setAside = String(values.setAside);
  if (values.department) params.department = String(values.department);
  if (values.state) params.state = String(values.state);
  if (values.daysOut) {
    const n = Number(values.daysOut);
    if (!isNaN(n) && n > 0) params.daysOut = n;
  }

  const openOnly = String(values.openOnly ?? 'yes');
  if (openOnly === 'yes') params.openOnly = true;
  else if (openOnly === 'no') params.openOnly = false;
  // 'all' => omit param

  if (sortModel.length > 0) {
    params.sortBy = sortModel[0].field;
    params.sortDescending = sortModel[0].sort === 'desc';
  }

  return params;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const RESPONSIVE_COLUMNS: ResponsiveColumnConfig = {
  departmentName: 'md',
  popState: 'md',
  naicsCode: 'lg',
  baseAndAllOptions: 'md',
  solicitationNumber: 'lg',
  actions: 'sm',
};

export default function OpportunitySearchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { enqueueSnackbar } = useSnackbar();
  const columnVisibility = useResponsiveColumns(RESPONSIVE_COLUMNS);

  const ignoreMutation = useIgnoreOpportunity();
  const unignoreMutation = useUnignoreOpportunity();
  const { data: ignoredIds } = useIgnoredOpportunityIds();
  const ignoredSet = useMemo(() => new Set(ignoredIds ?? []), [ignoredIds]);
  const [showIgnored, setShowIgnored] = useState(false);

  // --- Filter state from URL (committed = what drives the query) ---
  const committedValues = useMemo(() => readFiltersFromParams(searchParams), [searchParams]);

  // --- Local editing state (what the user types before clicking Search) ---
  const [editingValues, setEditingValues] = useState(committedValues);

  // Sync editingValues when committedValues changes (browser back/forward)
  useEffect(() => {
    setEditingValues(committedValues);
  }, [committedValues]);

  // Pagination & sort use local state so DataGrid gets synchronous updates.
  // URL is the source of truth on mount and browser back/forward; local state
  // is updated immediately on user interaction to avoid the double-fire bug
  // where DataGrid resets page to 0 before the URL-derived prop catches up.
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>(() => ({
    page: Number(searchParams.get('page') ?? 0),
    pageSize: Number(searchParams.get('pageSize') ?? 25),
  }));

  const [sortModel, setSortModel] = useState<GridSortModel>(() => {
    const sortBy = searchParams.get('sortBy');
    const sortDesc = searchParams.get('sortDesc');
    return sortBy ? [{ field: sortBy, sort: sortDesc === 'true' ? 'desc' : 'asc' }] : [];
  });

  // Sync from URL on browser back/forward
  useEffect(() => {
    const urlPage = Number(searchParams.get('page') ?? 0);
    const urlPageSize = Number(searchParams.get('pageSize') ?? 25);
    setPaginationModel((prev) =>
      prev.page === urlPage && prev.pageSize === urlPageSize ? prev : { page: urlPage, pageSize: urlPageSize },
    );
    const sortBy = searchParams.get('sortBy');
    const sortDesc = searchParams.get('sortDesc');
    const urlSort: GridSortModel = sortBy ? [{ field: sortBy, sort: sortDesc === 'true' ? 'desc' : 'asc' }] : [];
    setSortModel((prev) => {
      if (prev.length === 0 && urlSort.length === 0) return prev;
      if (prev.length === 1 && urlSort.length === 1 && prev[0].field === urlSort[0].field && prev[0].sort === urlSort[0].sort) return prev;
      return urlSort;
    });
  }, [searchParams]);

  // --- API params ---
  const apiParams = useMemo(() => {
    const params = filtersToApiParams(committedValues, paginationModel, sortModel);
    if (showIgnored) params.excludeIgnored = false;
    return params;
  }, [committedValues, paginationModel, sortModel, showIgnored]);

  // --- Query ---
  const {
    data,
    isLoading,
    isFetching,
    isError,
    refetch,
  } = useQuery({
    queryKey: queryKeys.opportunities.list(apiParams as unknown as Record<string, unknown>),
    queryFn: () => searchOpportunities(apiParams),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60 * 1000,
  });

  // --- Track mutation ---
  const trackMutation = useMutation({
    mutationFn: (noticeId: string) => createProspect({ noticeId }),
    onSuccess: () => {
      enqueueSnackbar('Opportunity added to pipeline', { variant: 'success' });
    },
    onError: () => {
      enqueueSnackbar('Failed to track opportunity', { variant: 'error' });
    },
  });

  // --- Handlers ---
  const updateUrl = useCallback(
    (
      newFilters: Record<string, unknown>,
      newPagination?: GridPaginationModel,
      newSort?: GridSortModel,
    ) => {
      const params = writeFiltersToParams(newFilters);
      const pg = newPagination ?? paginationModel;
      const sm = newSort ?? sortModel;
      if (pg.page > 0) params.set('page', String(pg.page));
      if (pg.pageSize !== 25) params.set('pageSize', String(pg.pageSize));
      if (sm.length > 0) {
        params.set('sortBy', sm[0].field);
        if (sm[0].sort === 'desc') params.set('sortDesc', 'true');
      }
      setSearchParams(params, { replace: true });
    },
    [paginationModel, sortModel, setSearchParams],
  );

  const handleFilterChange = useCallback(
    (key: string, value: unknown) => {
      setEditingValues((prev) => ({
        ...prev,
        [key]: value != null && value !== '' ? value : undefined,
      }));
    },
    [],
  );

  const handleClearFilters = useCallback(() => {
    setEditingValues({});
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  const handleSearch = useCallback(() => {
    // Commit editingValues to URL params, reset page to 0
    const params = writeFiltersToParams(editingValues);
    // Preserve sort from current URL
    if (sortModel.length > 0) {
      params.set('sortBy', sortModel[0].field);
      if (sortModel[0].sort === 'desc') params.set('sortDesc', 'true');
    }
    if (paginationModel.pageSize !== 25) params.set('pageSize', String(paginationModel.pageSize));
    setSearchParams(params, { replace: true });
  }, [editingValues, sortModel, paginationModel.pageSize, setSearchParams]);

  const handlePaginationChange = useCallback(
    (model: GridPaginationModel) => {
      setPaginationModel(model);
      updateUrl(committedValues, model, sortModel);
    },
    [committedValues, sortModel, updateUrl],
  );

  const handleSortChange = useCallback(
    (model: GridSortModel) => {
      setSortModel(model);
      const resetPage = { ...paginationModel, page: 0 };
      setPaginationModel(resetPage);
      updateUrl(committedValues, resetPage, model);
    },
    [committedValues, paginationModel, updateUrl],
  );

  const handleRowClick = useCallback(
    (params: GridRowParams<OpportunitySearchResult>) => {
      navigate(`/opportunities/${encodeURIComponent(params.row.noticeId)}`);
    },
    [navigate],
  );

  const handleExport = useCallback(async () => {
    try {
      const blob = await exportOpportunities(apiParams);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'opportunities.csv';
      a.click();
      URL.revokeObjectURL(url);
      enqueueSnackbar('Export downloaded', { variant: 'success' });
    } catch {
      enqueueSnackbar('Export failed', { variant: 'error' });
    }
  }, [apiParams, enqueueSnackbar]);

  const handleSaveSearch = useCallback(() => {
    // Placeholder — SaveSearchModal will be wired in a future phase
    console.log('Save search clicked. Filters:', committedValues);
    enqueueSnackbar('Save Search will be available soon', { variant: 'info' });
  }, [committedValues, enqueueSnackbar]);

  // --- Columns ---
  const columns: GridColDef<OpportunitySearchResult>[] = useMemo(
    () => [
      {
        field: 'title',
        headerName: 'Title',
        flex: 2,
        minWidth: 250,
        renderCell: (params) => (
          <Typography
            variant="body2"
            sx={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              color: 'primary.main',
              cursor: 'pointer',
            }}
          >
            {params.value ?? '--'}
          </Typography>
        ),
      },
      {
        field: 'solicitationNumber',
        headerName: 'Solicitation #',
        width: 150,
        valueGetter: (_value, row) => row.solicitationNumber ?? '--',
      },
      {
        field: 'departmentName',
        headerName: 'Department',
        width: 180,
        renderCell: (params) => (
          <AgencyLink name={params.row.departmentName} agencyCode={params.row.contractingOfficeId ?? undefined} />
        ),
        valueGetter: (_value, row) => row.departmentName ?? '--',
      },
      {
        field: 'setAsideDescription',
        headerName: 'Set-Aside',
        width: 160,
        renderCell: (params) => {
          const code = params.row.setAsideCode;
          const desc = params.row.setAsideDescription;
          if (!desc && !code) return '--';
          const chipProps = getSetAsideChipProps(code);
          return (
            <Chip
              label={desc ?? code ?? ''}
              size="small"
              color={chipProps.color}
              sx={chipProps.sx}
            />
          );
        },
        sortable: false,
      },
      {
        field: 'naicsCode',
        headerName: 'NAICS',
        width: 90,
        valueGetter: (_value, row) => row.naicsCode ?? '--',
      },
      {
        field: 'responseDeadline',
        headerName: 'Response Deadline',
        width: 170,
        renderCell: (params) => {
          const deadline = params.row.responseDeadline;
          const daysUntil = params.row.daysUntilDue;
          if (!deadline) return '--';

          const dateStr = new Date(deadline).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          });

          const isExpired = daysUntil != null && daysUntil < 0;
          const isUrgent = daysUntil != null && daysUntil >= 0 && daysUntil < 7;

          let daysLabel = '';
          if (daysUntil != null) {
            if (isExpired) daysLabel = 'Expired';
            else if (daysUntil === 0) daysLabel = 'Due today';
            else daysLabel = `${daysUntil}d`;
          }

          return (
            <Box>
              <Typography variant="body2">{dateStr}</Typography>
              {daysLabel && (
                <Typography
                  variant="caption"
                  sx={{
                    color: isExpired ? 'text.disabled' : isUrgent ? 'error.main' : 'text.secondary',
                    fontWeight: isUrgent ? 700 : 400,
                  }}
                >
                  {daysLabel}
                </Typography>
              )}
            </Box>
          );
        },
      },
      {
        field: 'baseAndAllOptions',
        headerName: 'Award Ceiling',
        width: 140,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params) => (
          <CurrencyDisplay value={params.row.baseAndAllOptions} compact />
        ),
      },
      {
        field: 'popState',
        headerName: 'POP State',
        width: 90,
        valueGetter: (_value, row) => row.popState ?? '--',
      },
      {
        field: 'actions',
        headerName: '',
        width: 160,
        sortable: false,
        renderCell: (params) => {
          const isIgnored = ignoredSet.has(params.row.noticeId);
          return (
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <Button
                size="small"
                variant="outlined"
                startIcon={<TrackChangesIcon />}
                onClick={(e) => {
                  e.stopPropagation();
                  trackMutation.mutate(params.row.noticeId);
                }}
                disabled={trackMutation.isPending || !!params.row.prospectStatus}
              >
                {params.row.prospectStatus ? 'Tracked' : 'Track'}
              </Button>
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  if (isIgnored) {
                    unignoreMutation.mutate(params.row.noticeId, {
                      onSuccess: () => enqueueSnackbar('Opportunity restored', { variant: 'info' }),
                      onError: () => enqueueSnackbar('Failed to restore opportunity', { variant: 'error' }),
                    });
                  } else {
                    ignoreMutation.mutate(
                      { noticeId: params.row.noticeId },
                      {
                        onSuccess: () => enqueueSnackbar('Opportunity ignored', { variant: 'info' }),
                        onError: () => enqueueSnackbar('Failed to ignore opportunity', { variant: 'error' }),
                      },
                    );
                  }
                }}
                disabled={ignoreMutation.isPending || unignoreMutation.isPending}
                title={isIgnored ? 'Un-ignore' : 'Ignore'}
                color={isIgnored ? 'warning' : 'default'}
              >
                {isIgnored ? <VisibilityIcon fontSize="small" /> : <VisibilityOffIcon fontSize="small" />}
              </IconButton>
            </Box>
          );
        },
      },
    ],
    [trackMutation, ignoredSet, ignoreMutation, unignoreMutation],
  );

  // --- Render ---
  if (isError) {
    return (
      <Box>
        <PageHeader title="Opportunity Search" />
        <ErrorState
          title="Failed to load opportunities"
          message="An error occurred while searching for opportunities. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="Opportunity Search"
        subtitle="Search federal contract opportunities from SAM.gov"
        actions={
          <>
            <Button
              variant="outlined"
              startIcon={<BookmarkAddIcon />}
              onClick={handleSaveSearch}
            >
              Save Search
            </Button>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={handleExport}
            >
              Export CSV
            </Button>
          </>
        }
      />

      <SearchFilters
        filters={FILTER_CONFIGS}
        values={editingValues}
        onChange={handleFilterChange}
        onClear={handleClearFilters}
        onSearch={handleSearch}
      />

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1, flexWrap: 'wrap', gap: 1 }}>
        <Typography variant="body2" color="text.secondary">
          {data ? `${data.totalCount.toLocaleString()} results` : ''}
        </Typography>
        <FormControlLabel
          control={<Switch size="small" checked={showIgnored} onChange={(_, v) => setShowIgnored(v)} />}
          label="Show ignored"
          sx={{ ml: 'auto' }}
        />
      </Box>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        loading={isLoading || isFetching}
        rowCount={data?.totalCount ?? 0}
        paginationModel={paginationModel}
        onPaginationModelChange={handlePaginationChange}
        sortModel={sortModel}
        onSortModelChange={handleSortChange}
        onRowClick={handleRowClick}
        getRowId={(row: OpportunitySearchResult) => row.noticeId}
        columnVisibilityModel={columnVisibility}
        sx={{ minHeight: 400 }}
      />
    </Box>
  );
}
