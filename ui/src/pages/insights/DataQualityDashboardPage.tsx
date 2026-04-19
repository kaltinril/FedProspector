import { useMemo } from 'react';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import type { GridColDef } from '@mui/x-data-grid';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlined';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutlined';
import StorageIcon from '@mui/icons-material/Storage';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { DataTable } from '@/components/shared/DataTable';
import { useDataQualityDashboard } from '@/queries/useInsights';
import { formatDateTime } from '@/utils/dateFormatters';
import type {
  DataFreshnessDto,
  DataCompletenessDto,
  CrossSourceValidationDto,
} from '@/types/insights';

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

function freshnessChip(status: string) {
  switch (status.toUpperCase()) {
    case 'FRESH':
      return <Chip label="Fresh" size="small" color="success" />;
    case 'STALE':
      return <Chip label="Stale" size="small" color="warning" />;
    case 'CRITICAL':
      return <Chip label="Critical" size="small" color="error" />;
    default:
      return <Chip label={status} size="small" />;
  }
}

function validationChip(status: string) {
  switch (status.toUpperCase()) {
    case 'OK':
      return <Chip label="OK" size="small" color="success" />;
    case 'WARNING':
      return <Chip label="Warning" size="small" color="warning" />;
    case 'ERROR':
      return <Chip label="Error" size="small" color="error" />;
    default:
      return <Chip label={status} size="small" />;
  }
}

function completenessColor(pct: number): 'success' | 'warning' | 'error' {
  if (pct >= 90) return 'success';
  if (pct >= 70) return 'warning';
  return 'error';
}

// ---------------------------------------------------------------------------
// Summary Card
// ---------------------------------------------------------------------------

function SummaryCard({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <Card>
      <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box
          sx={{
            bgcolor: color,
            color: 'common.white',
            borderRadius: 2,
            p: 1.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {icon}
        </Box>
        <Box>
          <Typography variant="h5" sx={{
            fontWeight: "bold"
          }}>
            {value}
          </Typography>
          <Typography variant="body2" sx={{
            color: "text.secondary"
          }}>
            {title}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Freshness columns
// ---------------------------------------------------------------------------

const freshnessColumns: GridColDef<DataFreshnessDto>[] = [
  { field: 'sourceName', headerName: 'Source', flex: 1, minWidth: 150 },
  { field: 'tableName', headerName: 'Table', width: 180, valueGetter: (_v, row) => row.tableName ?? '--' },
  {
    field: 'lastLoadDate',
    headerName: 'Last Load',
    width: 180,
    valueGetter: (_v, row) => row.lastLoadDate,
    renderCell: (params) => (
      <Typography variant="body2">
        {params.value ? formatDateTime(params.value as string) : '--'}
      </Typography>
    ),
  },
  {
    field: 'hoursSinceLastLoad',
    headerName: 'Hours Ago',
    width: 100,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_v, row) => row.hoursSinceLastLoad ?? 0,
  },
  {
    field: 'freshnessStatus',
    headerName: 'Status',
    width: 110,
    renderCell: (params) => freshnessChip(params.value as string),
  },
  {
    field: 'recordsLoaded',
    headerName: 'Last Load Rows',
    width: 130,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_v, row) => row.recordsLoaded.toLocaleString(),
  },
  {
    field: 'tableRowCount',
    headerName: 'Total Rows',
    width: 120,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_v, row) => row.tableRowCount?.toLocaleString() ?? '--',
  },
  {
    field: 'lastLoadStatus',
    headerName: 'Load Status',
    width: 110,
    valueGetter: (_v, row) => row.lastLoadStatus ?? '--',
  },
];

// ---------------------------------------------------------------------------
// Completeness columns
// ---------------------------------------------------------------------------

const completenessColumns: GridColDef<DataCompletenessDto>[] = [
  { field: 'tableName', headerName: 'Table', width: 180 },
  { field: 'fieldName', headerName: 'Field', flex: 1, minWidth: 150 },
  {
    field: 'totalRows',
    headerName: 'Total Rows',
    width: 120,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_v, row) => row.totalRows.toLocaleString(),
  },
  {
    field: 'nonNullCount',
    headerName: 'Non-Null',
    width: 110,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_v, row) => row.nonNullCount.toLocaleString(),
  },
  {
    field: 'completenessPct',
    headerName: 'Completeness',
    width: 180,
    renderCell: (params) => {
      const pct = params.row.completenessPct;
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
          <LinearProgress
            variant="determinate"
            value={pct}
            color={completenessColor(pct)}
            sx={{ flexGrow: 1, height: 8, borderRadius: 1 }}
          />
          <Typography variant="caption" sx={{ minWidth: 40, textAlign: 'right' }}>
            {pct.toFixed(1)}%
          </Typography>
        </Box>
      );
    },
  },
];

// ---------------------------------------------------------------------------
// Validation columns
// ---------------------------------------------------------------------------

const validationColumns: GridColDef<CrossSourceValidationDto>[] = [
  { field: 'checkName', headerName: 'Check', flex: 1, minWidth: 200 },
  { field: 'sourceAName', headerName: 'Source A', width: 150 },
  {
    field: 'sourceACount',
    headerName: 'Count A',
    width: 110,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_v, row) => row.sourceACount.toLocaleString(),
  },
  { field: 'sourceBName', headerName: 'Source B', width: 150 },
  {
    field: 'sourceBCount',
    headerName: 'Count B',
    width: 110,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_v, row) => row.sourceBCount.toLocaleString(),
  },
  {
    field: 'difference',
    headerName: 'Diff',
    width: 100,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_v, row) => row.difference.toLocaleString(),
  },
  {
    field: 'pctDifference',
    headerName: '% Diff',
    width: 90,
    align: 'right',
    headerAlign: 'right',
    valueGetter: (_v, row) => `${row.pctDifference.toFixed(1)}%`,
  },
  {
    field: 'status',
    headerName: 'Status',
    width: 110,
    renderCell: (params) => validationChip(params.value as string),
  },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DataQualityDashboardPage() {
  const { data, isLoading, isError, refetch } = useDataQualityDashboard();

  const summaryStats = useMemo(() => {
    if (!data) return null;
    const freshness = data.freshness;
    const totalSources = freshness.length;
    const freshCount = freshness.filter((f) => f.freshnessStatus.toUpperCase() === 'FRESH').length;
    const staleCount = freshness.filter((f) => f.freshnessStatus.toUpperCase() === 'STALE').length;
    const criticalCount = freshness.filter((f) => f.freshnessStatus.toUpperCase() === 'CRITICAL').length;
    const healthScore = totalSources > 0 ? Math.round((freshCount / totalSources) * 100) : 0;
    return { totalSources, freshCount, staleCount, criticalCount, healthScore };
  }, [data]);

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => refetch()} />;

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader title="Data Quality" subtitle="Monitor data freshness, completeness, and cross-source validation" />

      {/* Summary Cards */}
      {summaryStats && (
        <Grid container spacing={{ xs: 1.5, sm: 2, md: 3 }} sx={{ mb: 3 }}>
          <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
            <SummaryCard
              title="Total Sources"
              value={summaryStats.totalSources}
              icon={<StorageIcon />}
              color="#1976d2"
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
            <SummaryCard
              title="Fresh"
              value={summaryStats.freshCount}
              icon={<CheckCircleOutlineIcon />}
              color="#2e7d32"
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
            <SummaryCard
              title="Stale"
              value={summaryStats.staleCount}
              icon={<WarningAmberIcon />}
              color="#ed6c02"
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
            <SummaryCard
              title="Critical"
              value={summaryStats.criticalCount}
              icon={<ErrorOutlineIcon />}
              color="#d32f2f"
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 4, md: 2.4 }}>
            <SummaryCard
              title="Health Score"
              value={`${summaryStats.healthScore}%`}
              icon={<CheckCircleOutlineIcon />}
              color={summaryStats.healthScore >= 80 ? '#2e7d32' : summaryStats.healthScore >= 50 ? '#ed6c02' : '#d32f2f'}
            />
          </Grid>
        </Grid>
      )}

      {/* Data Freshness */}
      <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Data Freshness
        </Typography>
        <DataTable
          columns={freshnessColumns}
          rows={data.freshness}
          getRowId={(row: DataFreshnessDto) => `${row.sourceName}-${row.tableName ?? ''}`}
          sx={{ maxHeight: 400 }}
        />
      </Paper>

      {/* Field Completeness */}
      <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Field Completeness
        </Typography>
        <DataTable
          columns={completenessColumns}
          rows={data.completeness}
          getRowId={(row: DataCompletenessDto) => `${row.tableName}-${row.fieldName}`}
          sx={{ maxHeight: 500 }}
        />
      </Paper>

      {/* Cross-Source Validation */}
      <Paper sx={{ p: { xs: 2, md: 3 } }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Cross-Source Validation
        </Typography>
        <DataTable
          columns={validationColumns}
          rows={data.validation}
          getRowId={(row: CrossSourceValidationDto) => row.checkId}
          sx={{ maxHeight: 400 }}
        />
      </Paper>
    </Box>
  );
}
