import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, keepPreviousData } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import type { GridColDef, GridPaginationModel, GridSortModel, GridRowParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';

import { PageHeader } from '@/components/shared/PageHeader';
import { SearchFilters } from '@/components/shared/SearchFilters';
import type { FilterConfig } from '@/components/shared/SearchFilters';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { CurrencyDisplay } from '@/components/shared/CurrencyDisplay';
import { getTargetOpportunities } from '@/api/opportunities';
import { createProspect } from '@/api/prospects';
import { queryKeys } from '@/queries/queryKeys';
import type { TargetOpportunityDto, TargetSearchParams } from '@/types/api';
import { getSetAsideChipProps } from '@/utils/constants';

// ---------------------------------------------------------------------------
// Filter configuration
// ---------------------------------------------------------------------------

const SET_ASIDE_OPTIONS = [
  { value: 'WOSB', label: 'WOSB' },
  { value: 'EDWOSB', label: 'EDWOSB' },
  { value: '8(A)', label: '8(a)' },
  { value: 'HUBZone', label: 'HUBZone' },
  { value: 'SDVOSB', label: 'SDVOSB' },
  { value: 'SBA', label: 'Total Small Business' },
];

const FILTER_CONFIGS: FilterConfig[] = [
  { key: 'naicsSector', label: 'NAICS Sector', type: 'text' },
  { key: 'setAside', label: 'Set-Aside', type: 'select', options: SET_ASIDE_OPTIONS },
  { key: 'department', label: 'Department', type: 'text' },
  { key: 'state', label: 'State (POP)', type: 'text' },
  { key: 'minValue', label: 'Min Value', type: 'text' },
  { key: 'maxValue', label: 'Max Value', type: 'text' },
];

// ---------------------------------------------------------------------------
// URL <-> filter helpers
// ---------------------------------------------------------------------------

const FILTER_KEYS = ['naicsSector', 'setAside', 'department', 'state', 'minValue', 'maxValue'] as const;

function readFiltersFromParams(params: URLSearchParams): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  for (const key of FILTER_KEYS) {
    const v = params.get(key);
    if (v != null && v !== '') {
      values[key] = v;
    }
  }
  return values;
}

function writeFiltersToParams(values: Record<string, unknown>): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const v = values[key];
    if (v != null && v !== '') {
      params.set(key, String(v));
    }
  }
  return params;
}

function filtersToApiParams(
  values: Record<string, unknown>,
  pagination: GridPaginationModel,
  sortModel: GridSortModel,
): TargetSearchParams {
  const params: TargetSearchParams = {
    page: pagination.page + 1,
    pageSize: pagination.pageSize,
  };

  if (values.naicsSector) params.naicsSector = String(values.naicsSector);
  if (values.setAside) params.setAside = String(values.setAside);
  if (values.department) params.department = String(values.department);
  if (values.state) params.state = String(values.state);
  if (values.minValue) {
    const n = Number(values.minValue);
    if (!isNaN(n) && n > 0) params.minValue = n;
  }
  if (values.maxValue) {
    const n = Number(values.maxValue);
    if (!isNaN(n) && n > 0) params.maxValue = n;
  }

  if (sortModel.length > 0) {
    params.sortBy = sortModel[0].field;
    params.sortDescending = sortModel[0].sort === 'desc';
  }

  return params;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TargetOpportunityPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { enqueueSnackbar } = useSnackbar();

  // --- Filter state from URL (committed = drives the query) ---
  const committedValues = useMemo(() => readFiltersFromParams(searchParams), [searchParams]);

  // --- Local editing state (drives the input fields) ---
  const [editingValues, setEditingValues] = useState(committedValues);

  // Sync editing state when URL changes externally (browser back/forward)
  useEffect(() => {
    setEditingValues(committedValues);
  }, [committedValues]);

  const paginationModel: GridPaginationModel = useMemo(() => ({
    page: Number(searchParams.get('page') ?? 0),
    pageSize: Number(searchParams.get('pageSize') ?? 25),
  }), [searchParams]);

  const sortModel: GridSortModel = useMemo(() => {
    const sortBy = searchParams.get('sortBy');
    const sortDesc = searchParams.get('sortDesc');
    if (sortBy) {
      return [{ field: sortBy, sort: sortDesc === 'true' ? 'desc' : 'asc' }];
    }
    return [];
  }, [searchParams]);

  // --- API params ---
  const apiParams = useMemo(
    () => filtersToApiParams(committedValues, paginationModel, sortModel),
    [committedValues, paginationModel, sortModel],
  );

  // --- Query ---
  const {
    data,
    isLoading,
    isFetching,
    isError,
    refetch,
  } = useQuery({
    queryKey: queryKeys.opportunities.targets(apiParams as unknown as Record<string, unknown>),
    queryFn: () => getTargetOpportunities(apiParams),
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
      setEditingValues((prev) => {
        const next = { ...prev };
        if (value != null && value !== '') {
          next[key] = value;
        } else {
          delete next[key];
        }
        return next;
      });
    },
    [],
  );

  const handleClearFilters = useCallback(() => {
    setEditingValues({});
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  const handleSearch = useCallback(() => {
    const params = writeFiltersToParams(editingValues);
    // Preserve pagination size but reset to page 0
    if (paginationModel.pageSize !== 25) params.set('pageSize', String(paginationModel.pageSize));
    if (sortModel.length > 0) {
      params.set('sortBy', sortModel[0].field);
      if (sortModel[0].sort === 'desc') params.set('sortDesc', 'true');
    }
    setSearchParams(params, { replace: true });
  }, [editingValues, paginationModel.pageSize, sortModel, setSearchParams]);

  const handlePaginationChange = useCallback(
    (model: GridPaginationModel) => {
      updateUrl(committedValues, model, sortModel);
    },
    [committedValues, sortModel, updateUrl],
  );

  const handleSortChange = useCallback(
    (model: GridSortModel) => {
      updateUrl(committedValues, { ...paginationModel, page: 0 }, model);
    },
    [committedValues, paginationModel, updateUrl],
  );

  const handleRowClick = useCallback(
    (params: GridRowParams<TargetOpportunityDto>) => {
      navigate(`/opportunities/${encodeURIComponent(params.row.noticeId)}`);
    },
    [navigate],
  );

  // --- Columns ---
  const columns: GridColDef<TargetOpportunityDto>[] = useMemo(
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
        field: 'awardAmount',
        headerName: 'Award Value',
        width: 140,
        align: 'right',
        headerAlign: 'right',
        renderCell: (params) => (
          <CurrencyDisplay value={params.row.awardAmount} compact />
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
        width: 100,
        sortable: false,
        renderCell: (params) => (
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
        ),
      },
    ],
    [trackMutation],
  );

  // --- Render ---
  if (isError) {
    return (
      <Box>
        <PageHeader title="Target Opportunities" />
        <ErrorState
          title="Failed to load target opportunities"
          message="Could not retrieve opportunities matched to your company profile. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="Target Opportunities"
        subtitle="Opportunities matched to your company's NAICS codes, certifications, and past performance"
      />

      <SearchFilters
        filters={FILTER_CONFIGS}
        values={editingValues}
        onChange={handleFilterChange}
        onClear={handleClearFilters}
        onSearch={handleSearch}
      />

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="body2" color="text.secondary">
          {data ? `${data.totalCount.toLocaleString()} results` : ''}
        </Typography>
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
        getRowId={(row: TargetOpportunityDto) => row.noticeId}
        sx={{ minHeight: 400 }}
      />
    </Box>
  );
}
