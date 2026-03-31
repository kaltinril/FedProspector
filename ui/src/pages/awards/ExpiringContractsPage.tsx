import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { GridColDef, GridRowParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Link from '@mui/material/Link';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';
import SwapHorizOutlined from '@mui/icons-material/SwapHorizOutlined';

import { AgencyLink } from '@/components/shared/AgencyLink';
import { PageHeader } from '@/components/shared/PageHeader';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { getExpiringContracts } from '@/api/awards';
import { queryKeys } from '@/queries/queryKeys';
import { formatCurrency } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import { useResponsiveColumns } from '@/hooks/useResponsiveColumns';
import type { ResponsiveColumnConfig } from '@/hooks/useResponsiveColumns';
import type { ExpiringContractDto } from '@/types/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type ChipColor = 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning';

function monthsRemainingChip(months: number | null | undefined) {
  if (months == null) return <Chip label="--" size="small" color="default" />;
  let color: ChipColor = 'success';
  if (months < 3) color = 'error';
  else if (months < 6) color = 'warning';
  return <Chip label={`${months}mo`} size="small" color={color} />;
}

function percentSpentColor(pct: number | null | undefined): ChipColor {
  if (pct == null) return 'default';
  if (pct > 90) return 'error';
  if (pct >= 70) return 'warning';
  return 'success';
}

function incumbentStatusChip(status: string | null | undefined) {
  if (!status) return '--';
  const color: ChipColor = status === 'Active' ? 'success' : 'error';
  return <Chip label={status} size="small" color={color} variant="outlined" />;
}

function resolicitationChip(status: string | null | undefined) {
  if (!status || status === 'Not Yet Posted') {
    return <Chip label="Not Yet Posted" size="small" color="default" variant="outlined" />;
  }
  if (status === 'Pre-Solicitation') {
    return <Chip label="Pre-Solicitation" size="small" color="info" variant="outlined" />;
  }
  return <Chip label={status} size="small" color="success" variant="outlined" />;
}

function shiftIndicator(row: ExpiringContractDto) {
  if (row.shiftDetected == null) return null;
  if (!row.shiftDetected) return null;

  const label = row.predecessorSetAsideType
    ? `Set-aside shifted from ${row.predecessorSetAsideType}`
    : 'Set-aside shifted';

  return (
    <Tooltip title={label} arrow>
      <Chip
        icon={<SwapHorizOutlined fontSize="small" />}
        label="Shifted"
        size="small"
        color="warning"
        variant="filled"
        sx={{ ml: 0.5 }}
      />
    </Tooltip>
  );
}

function truncate(text: string | null | undefined, maxLen: number): string {
  if (!text) return '--';
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '...';
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

function buildColumns(navigate: ReturnType<typeof useNavigate>): GridColDef<ExpiringContractDto>[] {
  return [
    {
      field: 'piid',
      headerName: 'Contract ID',
      flex: 1,
      minWidth: 150,
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
    {
      field: 'source',
      headerName: 'Source',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          color={params.value === 'FPDS' ? 'primary' : 'secondary'}
          variant="outlined"
        />
      ),
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1.5,
      minWidth: 180,
      valueFormatter: (value: string | null | undefined) => truncate(value, 60),
    },
    {
      field: 'agencyName',
      headerName: 'Agency',
      flex: 1,
      minWidth: 140,
      renderCell: (params) => params.row.agencyName ? <AgencyLink name={params.row.agencyName} /> : '--',
    },
    {
      field: 'naicsCode',
      headerName: 'NAICS',
      width: 90,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'vendorName',
      headerName: 'Vendor',
      flex: 1,
      minWidth: 140,
      renderCell: (params) => {
        const uei = params.row.vendorUei;
        const name = params.row.vendorName;
        if (!name) return '--';
        if (!uei) return <Typography variant="body2">{name}</Typography>;
        return (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/entities/${encodeURIComponent(uei)}`);
            }}
          >
            {name}
          </Link>
        );
      },
    },
    {
      field: 'contractValue',
      headerName: 'Contract Value',
      width: 130,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value, true),
    },
    {
      field: 'completionDate',
      headerName: 'Completion Date',
      width: 130,
      valueFormatter: (value: string | null | undefined) => formatDate(value),
    },
    {
      field: 'monthsRemaining',
      headerName: 'Months Left',
      width: 110,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => monthsRemainingChip(params.value as number | null | undefined),
    },
    {
      field: 'monthlyBurnRate',
      headerName: 'Burn Rate',
      width: 120,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => {
        if (value == null) return '--';
        return `${formatCurrency(value, true)}/mo`;
      },
    },
    {
      field: 'percentSpent',
      headerName: '% Spent',
      width: 100,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => {
        const pct = params.value as number | null | undefined;
        if (pct == null) return '--';
        return (
          <Chip
            label={`${pct.toFixed(0)}%`}
            size="small"
            color={percentSpentColor(pct)}
            variant="outlined"
          />
        );
      },
    },
    {
      field: 'registrationStatus',
      headerName: 'Incumbent Status',
      width: 140,
      renderCell: (params) => incumbentStatusChip(params.value as string | null | undefined),
      sortable: false,
    },
    {
      field: 'resolicitationStatus',
      headerName: 'Re-solicitation',
      width: 190,
      renderCell: (params) => (
        <Box sx={{ display: 'flex', alignItems: 'center', overflow: 'hidden' }}>
          {resolicitationChip(params.value as string | null | undefined)}
          {shiftIndicator(params.row)}
        </Box>
      ),
      sortable: false,
    },
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const MONTHS_OPTIONS = [
  { value: 3, label: '3 months' },
  { value: 6, label: '6 months' },
  { value: 12, label: '12 months' },
  { value: 18, label: '18 months' },
];

const RESPONSIVE_COLUMNS: ResponsiveColumnConfig = {
  agencyName: 'md',
  naicsCode: 'lg',
  vendorName: 'md',
  monthlyBurnRate: 'lg',
  percentSpent: 'lg',
  registrationStatus: 'lg',
  resolicitationStatus: 'md',
};

export default function ExpiringContractsPage() {
  const navigate = useNavigate();
  const [monthsAhead, setMonthsAhead] = useState(12);
  const columnVisibility = useResponsiveColumns(RESPONSIVE_COLUMNS);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.awards.expiring({ monthsAhead }),
    queryFn: () => getExpiringContracts({ monthsAhead, limit: 50 }),
    staleTime: 5 * 60 * 1000,
  });

  const columns = useMemo(() => buildColumns(navigate), [navigate]);

  const handleMonthsChange = useCallback((e: SelectChangeEvent<number>) => {
    setMonthsAhead(Number(e.target.value));
  }, []);

  const handleRowClick = useCallback(
    (params: GridRowParams<ExpiringContractDto>) => {
      navigate(`/awards/${encodeURIComponent(params.row.piid)}`);
    },
    [navigate],
  );

  if (isError) {
    return (
      <Box>
        <PageHeader
          title="Expiring Contracts"
          subtitle="Re-compete displacement opportunities"
        />
        <ErrorState
          title="Failed to load expiring contracts"
          message="Could not retrieve contract expiration data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="Expiring Contracts"
        subtitle="Re-compete displacement opportunities"
      />

      {/* Filter bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel id="months-ahead-label">Expiring within</InputLabel>
          <Select
            labelId="months-ahead-label"
            value={monthsAhead}
            label="Expiring within"
            onChange={handleMonthsChange}
          >
            {MONTHS_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {data && (
          <Chip
            label={`${data.length} contract${data.length !== 1 ? 's' : ''}`}
            color="primary"
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {isLoading && <LoadingState message="Loading expiring contracts..." />}

      {!isLoading && (
        <DataTable
          columns={columns}
          rows={data ?? []}
          loading={false}
          onRowClick={handleRowClick}
          getRowId={(row: ExpiringContractDto) => `${row.source}-${row.piid}`}
          columnVisibilityModel={columnVisibility}
          sx={{ minHeight: 400 }}
        />
      )}
    </Box>
  );
}
