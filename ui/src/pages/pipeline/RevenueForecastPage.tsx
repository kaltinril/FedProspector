import { useMemo } from 'react';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { BarChart } from '@mui/x-charts/BarChart';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { DataTable } from '@/components/shared/DataTable';
import { useRevenueForecast } from '@/queries/usePipeline';
import { formatCurrency, formatPercent } from '@/utils/formatters';
import type { RevenueForecastDto } from '@/types/pipeline';
import type { GridColDef } from '@mui/x-data-grid';

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

const columns: GridColDef[] = [
  {
    field: 'forecastMonth',
    headerName: 'Month',
    width: 130,
  },
  {
    field: 'prospectCount',
    headerName: 'Prospects',
    width: 110,
    align: 'right',
    headerAlign: 'right',
  },
  {
    field: 'totalUnweightedValue',
    headerName: 'Unweighted Total',
    width: 160,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => (
      <Typography variant="body2">
        {formatCurrency(params.value as number | null, true)}
      </Typography>
    ),
  },
  {
    field: 'totalWeightedValue',
    headerName: 'Weighted Total',
    width: 160,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => (
      <Typography variant="body2" fontWeight={600}>
        {formatCurrency(params.value as number | null, true)}
      </Typography>
    ),
  },
  {
    field: 'avgWinProbability',
    headerName: 'Avg Win Prob.',
    width: 130,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => (
      <Typography variant="body2">
        {formatPercent(params.value as number | null)}
      </Typography>
    ),
  },
];

// ---------------------------------------------------------------------------
// RevenueForecastPage
// ---------------------------------------------------------------------------

export default function RevenueForecastPage() {
  const { data: forecast, isLoading, isError, refetch } = useRevenueForecast();

  const chartData = useMemo(() => {
    if (!forecast) return [];
    return forecast.map((f) => ({
      month: f.forecastMonth,
      weighted: f.totalWeightedValue ?? 0,
      unweighted: f.totalUnweightedValue ?? 0,
    }));
  }, [forecast]);

  const totalWeighted = useMemo(() => {
    if (!forecast) return 0;
    return forecast.reduce((sum, f) => sum + (f.totalWeightedValue ?? 0), 0);
  }, [forecast]);

  const totalUnweighted = useMemo(() => {
    if (!forecast) return 0;
    return forecast.reduce((sum, f) => sum + (f.totalUnweightedValue ?? 0), 0);
  }, [forecast]);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  if (!forecast || forecast.length === 0) {
    return (
      <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
        <PageHeader title="Revenue Forecast" subtitle="Monthly pipeline projections" />
        <EmptyState
          title="No Forecast Data"
          message="Add prospects with estimated values and win probabilities to see forecasts."
        />
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader
        title="Revenue Forecast"
        subtitle="Monthly pipeline projections weighted by win probability"
      />

      {/* Summary */}
      <Grid container spacing={{ xs: 1.5, sm: 2, md: 3 }} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="h4" fontWeight={700} color="primary.main">
              {formatCurrency(totalWeighted, true)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Weighted Forecast
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="h4" fontWeight={700} color="text.secondary">
              {formatCurrency(totalUnweighted, true)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Unweighted Value
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Chart */}
      <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Monthly Forecast
        </Typography>
        {chartData.length > 0 ? (
          <Box sx={{ width: '100%', height: 350, overflowX: 'auto' }}>
            <BarChart
              dataset={chartData}
              xAxis={[{ scaleType: 'band', dataKey: 'month' }]}
              series={[
                {
                  dataKey: 'weighted',
                  label: 'Weighted',
                  valueFormatter: (v) => formatCurrency(v as number | null, true),
                },
                {
                  dataKey: 'unweighted',
                  label: 'Unweighted',
                  valueFormatter: (v) => formatCurrency(v as number | null, true),
                },
              ]}
            />
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No chart data available.
          </Typography>
        )}
      </Paper>

      {/* Table */}
      <Paper sx={{ p: { xs: 2, md: 3 } }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Details
        </Typography>
        <DataTable
          columns={columns}
          rows={forecast}
          getRowId={(row: RevenueForecastDto) => row.forecastMonth}
        />
      </Paper>
    </Box>
  );
}
