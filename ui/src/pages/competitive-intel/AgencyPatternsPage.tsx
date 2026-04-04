import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GridColDef, GridRowParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { PageHeader } from '@/components/shared/PageHeader';
import { useAgencyPatterns } from '@/queries/useCompetitiveIntel';
import { useDebounce } from '@/hooks/useDebounce';
import { formatPercent } from '@/utils/formatters';
import type { AgencyRecompetePatternDto } from '@/types/competitiveIntel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function metricBar(value: number | null | undefined) {
  if (value == null) return <Typography variant="body2">--</Typography>;
  const pct = Math.min(Math.max(value, 0), 100);
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
      />
      <Typography variant="body2" sx={{ minWidth: 50, textAlign: 'right' }}>
        {formatPercent(value)}
      </Typography>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

function buildColumns(): GridColDef<AgencyRecompetePatternDto>[] {
  return [
    {
      field: 'contractingOfficeName',
      headerName: 'Office',
      flex: 1.5,
      minWidth: 200,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'agencyName',
      headerName: 'Agency',
      flex: 1,
      minWidth: 160,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'totalContractsAnalyzed',
      headerName: 'Contracts',
      width: 100,
      align: 'center',
      headerAlign: 'center',
    },
    {
      field: 'incumbentRetentionRatePct',
      headerName: 'Incumbent Retention',
      width: 190,
      renderCell: (params) => metricBar(params.value as number | null),
    },
    {
      field: 'newVendorPenetrationPct',
      headerName: 'New Vendor Penetration',
      width: 180,
      renderCell: (params) => metricBar(params.value as number | null),
    },
    {
      field: 'soleSourceRatePct',
      headerName: 'Sole Source',
      width: 170,
      renderCell: (params) => metricBar(params.value as number | null),
    },
    {
      field: 'bridgeExtensionFrequencyPct',
      headerName: 'Bridge/Extension',
      width: 170,
      renderCell: (params) => metricBar(params.value as number | null),
    },
    {
      field: 'setAsideShiftFrequencyPct',
      headerName: 'Set-Aside Shift',
      width: 170,
      renderCell: (params) => metricBar(params.value as number | null),
    },
    {
      field: 'avgSolicitationLeadTimeDays',
      headerName: 'Avg Lead Time',
      width: 130,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) =>
        value != null ? `${Math.round(value)} days` : '--',
    },
    {
      field: 'naicsShiftRatePct',
      headerName: 'NAICS Shift',
      width: 160,
      renderCell: (params) => metricBar(params.value as number | null),
    },
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AgencyPatternsPage() {
  const navigate = useNavigate();
  const [agencyCode, setAgencyCode] = useState('');
  const [officeCode, setOfficeCode] = useState('');

  const debouncedAgency = useDebounce(agencyCode, 400);
  const debouncedOffice = useDebounce(officeCode, 400);

  const params = useMemo(
    () => ({
      agencyCode: debouncedAgency || undefined,
      officeCode: debouncedOffice || undefined,
    }),
    [debouncedAgency, debouncedOffice],
  );

  const { data, isLoading, isError, refetch } = useAgencyPatterns(params);
  const columns = useMemo(() => buildColumns(), []);

  const handleRowClick = useCallback(
    (rowParams: GridRowParams<AgencyRecompetePatternDto>) => {
      const id = rowParams.row.contractingOfficeId;
      if (id) {
        navigate(`/competitive-intel/offices/${encodeURIComponent(id)}`);
      }
    },
    [navigate],
  );

  if (isError) {
    return (
      <Box>
        <PageHeader title="Agency Re-compete Patterns" subtitle="How agencies handle re-competition" />
        <ErrorState
          title="Failed to load agency patterns"
          message="Could not retrieve pattern data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title="Agency Re-compete Patterns" subtitle="How agencies handle re-competition" />

      {/* Filter bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="Agency"
          value={agencyCode}
          onChange={(e) => setAgencyCode(e.target.value)}
          sx={{ minWidth: 180 }}
        />
        <TextField
          size="small"
          label="Office Code"
          value={officeCode}
          onChange={(e) => setOfficeCode(e.target.value)}
          sx={{ minWidth: 150 }}
        />
        {data && (
          <Chip
            label={`${data.length} office${data.length !== 1 ? 's' : ''}`}
            color="primary"
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {isLoading && <LoadingState message="Loading agency patterns..." />}

      {!isLoading && (
        <DataTable
          columns={columns}
          rows={data ?? []}
          loading={false}
          onRowClick={handleRowClick}
          getRowId={(row: AgencyRecompetePatternDto) => row.contractingOfficeId}
          sx={{ minHeight: 400 }}
        />
      )}
    </Box>
  );
}
