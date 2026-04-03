import { useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import type { GridColDef, GridRowParams } from '@mui/x-data-grid';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { DataTable } from '@/components/shared/DataTable';
import { StatusChip } from '@/components/shared/StatusChip';
import { useStaleProspects } from '@/queries/usePipeline';
import { formatCurrency } from '@/utils/formatters';
import { formatRelative } from '@/utils/dateFormatters';
import type { StaleProspectDto } from '@/types/pipeline';

// ---------------------------------------------------------------------------
// Staleness color
// ---------------------------------------------------------------------------

function stalenessColor(days: number): 'error' | 'warning' | 'default' {
  if (days >= 30) return 'error';
  if (days >= 14) return 'warning';
  return 'default';
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

const columns: GridColDef[] = [
  {
    field: 'opportunityTitle',
    headerName: 'Opportunity',
    flex: 2,
    minWidth: 200,
    valueGetter: (_value, row) => row.opportunityTitle ?? row.noticeId,
  },
  {
    field: 'status',
    headerName: 'Status',
    width: 130,
    renderCell: (params) => <StatusChip status={params.value as string} />,
  },
  {
    field: 'priority',
    headerName: 'Priority',
    width: 100,
    renderCell: (params) => {
      const p = (params.value as string | null)?.toUpperCase();
      if (!p) return '--';
      const colorMap: Record<string, 'error' | 'warning' | 'default'> = {
        CRITICAL: 'error',
        HIGH: 'error',
        MEDIUM: 'warning',
        LOW: 'default',
      };
      return <Chip label={p} size="small" color={colorMap[p] ?? 'default'} />;
    },
  },
  {
    field: 'daysSinceUpdate',
    headerName: 'Days Stale',
    width: 120,
    renderCell: (params) => {
      const days = params.value as number;
      return (
        <Chip
          label={`${days}d`}
          size="small"
          color={stalenessColor(days)}
        />
      );
    },
  },
  {
    field: 'assignedToName',
    headerName: 'Assigned To',
    width: 150,
    valueGetter: (_value, row) => row.assignedToName ?? '--',
  },
  {
    field: 'estimatedValue',
    headerName: 'Est. Value',
    width: 130,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_value, row) => row.estimatedValue,
    renderCell: (params) => (
      <Typography variant="body2">
        {formatCurrency(params.value as number | null, true)}
      </Typography>
    ),
  },
  {
    field: 'lastUpdatedAt',
    headerName: 'Last Updated',
    width: 150,
    valueGetter: (_value, row) => row.lastUpdatedAt,
    renderCell: (params) => (
      <Typography variant="body2" color="text.secondary">
        {formatRelative(params.value as string)}
      </Typography>
    ),
  },
];

// ---------------------------------------------------------------------------
// StaleProspectsPage
// ---------------------------------------------------------------------------

export default function StaleProspectsPage() {
  const navigate = useNavigate();
  const { data: staleProspects, isLoading, isError, refetch } = useStaleProspects();

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  if (!staleProspects || staleProspects.length === 0) {
    return (
      <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
        <PageHeader title="Stale Alerts" subtitle="Prospects needing attention" />
        <EmptyState
          title="No Stale Prospects"
          message="All prospects have been updated recently. No action needed."
        />
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader
        title="Stale Alerts"
        subtitle={`${staleProspects.length} prospect${staleProspects.length !== 1 ? 's' : ''} not updated in 14+ days`}
      />

      <DataTable
        columns={columns}
        rows={staleProspects}
        getRowId={(row: StaleProspectDto) => row.prospectId}
        onRowClick={(params: GridRowParams) => navigate(`/prospects/${params.id}`)}
        sortModel={[{ field: 'daysSinceUpdate', sort: 'desc' }]}
      />
    </Box>
  );
}
