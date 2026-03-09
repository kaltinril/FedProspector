import { useState, useCallback } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import Typography from '@mui/material/Typography';
import Collapse from '@mui/material/Collapse';
import type { GridColDef, GridPaginationModel, GridRowParams } from '@mui/x-data-grid';

import { useLoadHistory } from '@/queries/useAdmin';
import { DataTable } from '@/components/shared/DataTable';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { formatDateTime } from '@/utils/dateFormatters';
import { formatNumber } from '@/utils/formatters';
import { useResponsiveColumns } from '@/hooks/useResponsiveColumns';
import type { ResponsiveColumnConfig } from '@/hooks/useResponsiveColumns';
import type { LoadHistoryDto, LoadHistoryParams } from '@/types/api';

const STATUS_CHIP_MAP: Record<string, 'success' | 'error' | 'info' | 'default'> = {
  SUCCESS: 'success',
  FAILED: 'error',
  IN_PROGRESS: 'info',
};

const SOURCES = [
  { value: '', label: 'All Sources' },
  { value: 'sam_opportunities', label: 'SAM Opportunities' },
  { value: 'sam_entities', label: 'SAM Entities' },
  { value: 'sam_exclusions', label: 'SAM Exclusions' },
  { value: 'fpds', label: 'FPDS' },
  { value: 'usaspending', label: 'USASpending' },
  { value: 'subawards', label: 'Subawards' },
  { value: 'fedhier', label: 'Federal Hierarchy' },
  { value: 'gsa_calc', label: 'GSA CALC' },
];

const STATUSES = [
  { value: '', label: 'All Statuses' },
  { value: 'SUCCESS', label: 'Success' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'IN_PROGRESS', label: 'In Progress' },
];

const RESPONSIVE_COLUMNS: ResponsiveColumnConfig = {
  loadType: 'md',
  durationSeconds: 'md',
  recordsInserted: 'lg',
  recordsUpdated: 'lg',
  recordsErrored: 'lg',
  errorMessage: 'md',
};

export default function LoadHistoryTab() {
  const columnVisibility = useResponsiveColumns(RESPONSIVE_COLUMNS);
  const [filters, setFilters] = useState<LoadHistoryParams>({
    page: 1,
    pageSize: 25,
    days: 7,
  });
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const { data, isLoading, isError, refetch } = useLoadHistory(filters);

  const handlePaginationChange = useCallback((model: GridPaginationModel) => {
    setFilters((prev) => ({
      ...prev,
      page: model.page + 1,
      pageSize: model.pageSize,
    }));
  }, []);

  const handleRowClick = useCallback((params: GridRowParams<LoadHistoryDto>) => {
    const row = params.row;
    if (row.errorMessage) {
      setExpandedRow((prev) => (prev === row.loadId ? null : row.loadId));
    }
  }, []);

  const columns: GridColDef<LoadHistoryDto>[] = [
    {
      field: 'startedAt',
      headerName: 'Started',
      width: 170,
      renderCell: (params) => formatDateTime(params.value as string),
    },
    {
      field: 'sourceSystem',
      headerName: 'Source',
      width: 150,
    },
    {
      field: 'loadType',
      headerName: 'Type',
      width: 120,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value as string}
          color={STATUS_CHIP_MAP[params.value as string] ?? 'default'}
          size="small"
        />
      ),
    },
    {
      field: 'durationSeconds',
      headerName: 'Duration',
      width: 100,
      renderCell: (params) => {
        const secs = params.value as number | null;
        if (secs == null) return '--';
        if (secs < 60) return `${secs.toFixed(1)}s`;
        return `${(secs / 60).toFixed(1)}m`;
      },
    },
    {
      field: 'recordsRead',
      headerName: 'Read',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => formatNumber(params.value as number),
    },
    {
      field: 'recordsInserted',
      headerName: 'Inserted',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => formatNumber(params.value as number),
    },
    {
      field: 'recordsUpdated',
      headerName: 'Updated',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => formatNumber(params.value as number),
    },
    {
      field: 'recordsErrored',
      headerName: 'Errored',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => {
        const val = params.value as number;
        return (
          <Typography variant="body2" color={val > 0 ? 'error.main' : 'text.primary'}>
            {formatNumber(val)}
          </Typography>
        );
      },
    },
    {
      field: 'errorMessage',
      headerName: 'Error',
      flex: 1,
      minWidth: 150,
      renderCell: (params) => {
        const msg = params.value as string | null;
        if (!msg) return '--';
        return (
          <Typography variant="body2" color="error.main" noWrap title={msg}>
            {msg}
          </Typography>
        );
      },
    },
  ];

  if (isError) return <ErrorState onRetry={() => refetch()} />;

  return (
    <Box>
      {/* Filters */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <TextField
          select
          label="Source"
          value={filters.source ?? ''}
          onChange={(e) =>
            setFilters((prev) => ({
              ...prev,
              source: e.target.value || undefined,
              page: 1,
            }))
          }
          size="small"
          sx={{ minWidth: 180 }}
        >
          {SOURCES.map((s) => (
            <MenuItem key={s.value} value={s.value}>
              {s.label}
            </MenuItem>
          ))}
        </TextField>

        <TextField
          select
          label="Status"
          value={filters.status ?? ''}
          onChange={(e) =>
            setFilters((prev) => ({
              ...prev,
              status: e.target.value || undefined,
              page: 1,
            }))
          }
          size="small"
          sx={{ minWidth: 150 }}
        >
          {STATUSES.map((s) => (
            <MenuItem key={s.value} value={s.value}>
              {s.label}
            </MenuItem>
          ))}
        </TextField>

        <TextField
          label="Days"
          type="number"
          value={filters.days ?? 7}
          onChange={(e) =>
            setFilters((prev) => ({
              ...prev,
              days: parseInt(e.target.value, 10) || 7,
              page: 1,
            }))
          }
          size="small"
          sx={{ width: 100 }}
          slotProps={{ htmlInput: { min: 1, max: 365 } }}
        />
      </Box>

      {isLoading ? (
        <LoadingState variant="skeleton" rows={10} />
      ) : !data ? (
        <ErrorState onRetry={() => refetch()} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data.items}
            getRowId={(row: LoadHistoryDto) => row.loadId}
            rowCount={data.totalCount}
            paginationModel={{
              page: (filters.page ?? 1) - 1,
              pageSize: filters.pageSize ?? 25,
            }}
            onPaginationModelChange={handlePaginationChange}
            onRowClick={handleRowClick}
            columnVisibilityModel={columnVisibility}
          />

          {/* Expanded error detail */}
          {expandedRow != null && (
            <Collapse in={expandedRow != null}>
              <Box sx={{ p: 2, bgcolor: 'error.50', borderRadius: 1, mt: 1 }}>
                <Typography variant="subtitle2" color="error.main" gutterBottom>
                  Error Details (Load #{expandedRow})
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.8rem' }}
                >
                  {data.items.find((i) => i.loadId === expandedRow)?.errorMessage ?? 'No details'}
                </Typography>
              </Box>
            </Collapse>
          )}
        </>
      )}
    </Box>
  );
}
