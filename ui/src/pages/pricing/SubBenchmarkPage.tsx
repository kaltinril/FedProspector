import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { GridColDef } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { BarChart } from '@mui/x-charts/BarChart';

import { PageHeader } from '@/components/shared/PageHeader';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { getSubBenchmarks, getSubRatios } from '@/api/pricing';
import { queryKeys } from '@/queries/queryKeys';
import { formatCurrency } from '@/utils/formatters';
import { useDebounce } from '@/hooks/useDebounce';
import type { SubBenchmark } from '@/types/api';

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

function buildBenchmarkColumns(): GridColDef<SubBenchmark>[] {
  return [
    { field: 'subBusinessType', headerName: 'Business Type', flex: 1.2, minWidth: 180 },
    { field: 'naicsCode', headerName: 'NAICS', width: 100 },
    { field: 'agencyName', headerName: 'Agency', flex: 1, minWidth: 140 },
    {
      field: 'subCount',
      headerName: 'Count',
      width: 90,
      align: 'center',
      headerAlign: 'center',
    },
    {
      field: 'avgValue',
      headerName: 'Avg Value',
      width: 130,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number) => formatCurrency(value, true),
    },
    {
      field: 'totalValue',
      headerName: 'Total Value',
      width: 140,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number) => formatCurrency(value, true),
    },
    {
      field: 'minValue',
      headerName: 'Min Value',
      width: 120,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number) => formatCurrency(value, true),
    },
    {
      field: 'maxValue',
      headerName: 'Max Value',
      width: 120,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number) => formatCurrency(value, true),
    },
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SubBenchmarkPage() {
  const [naicsCode, setNaicsCode] = useState('');
  const [agencyName, setAgencyName] = useState('');

  const debouncedNaics = useDebounce(naicsCode, 400);
  const debouncedAgency = useDebounce(agencyName, 400);

  const benchmarkParams = useMemo(
    () => ({
      naicsCode: debouncedNaics || undefined,
      agencyName: debouncedAgency || undefined,
    }),
    [debouncedNaics, debouncedAgency],
  );

  const {
    data: benchmarks,
    isLoading: benchmarksLoading,
    isError: benchmarksError,
    refetch: refetchBenchmarks,
  } = useQuery({
    queryKey: queryKeys.pricing.subBenchmarks(benchmarkParams),
    queryFn: () => getSubBenchmarks(benchmarkParams),
    staleTime: 5 * 60 * 1000,
  });

  const {
    data: ratios,
    isLoading: ratiosLoading,
  } = useQuery({
    queryKey: queryKeys.pricing.subRatios(debouncedNaics || undefined),
    queryFn: () => getSubRatios(debouncedNaics || undefined),
    staleTime: 5 * 60 * 1000,
  });

  const benchmarkColumns = useMemo(() => buildBenchmarkColumns(), []);

  // Chart data for sub ratios
  const ratioChartData = useMemo(() => {
    if (!ratios?.length) return { naics: [] as string[], avgRatios: [] as number[] };
    return {
      naics: ratios.map((r) => r.naicsCode ?? ''),
      avgRatios: ratios.map((r) => r.avgSubRatio * 100),
    };
  }, [ratios]);

  const isLoading = benchmarksLoading || ratiosLoading;

  return (
    <Box>
      <PageHeader
        title="Subcontracting Benchmarks"
        subtitle="Subcontracting activity and sub-to-prime ratios by NAICS"
      />

      {/* Filters */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          size="small"
          label="NAICS Code"
          value={naicsCode}
          onChange={(e) => setNaicsCode(e.target.value)}
          sx={{ minWidth: 140 }}
        />
        <TextField
          size="small"
          label="Agency"
          value={agencyName}
          onChange={(e) => setAgencyName(e.target.value)}
          sx={{ minWidth: 200 }}
        />
        {benchmarks && (
          <Chip
            label={`${benchmarks.length} benchmark${benchmarks.length !== 1 ? 's' : ''}`}
            color="primary"
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {isLoading && <LoadingState message="Loading subcontracting data..." />}

      {benchmarksError && (
        <ErrorState
          title="Failed to load benchmarks"
          message="Could not retrieve subcontracting benchmark data."
          onRetry={() => refetchBenchmarks()}
        />
      )}

      {/* Benchmark table */}
      {!benchmarksLoading && benchmarks && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Subcontracting Benchmarks
          </Typography>
          <DataTable
            columns={benchmarkColumns}
            rows={benchmarks}
            loading={false}
            getRowId={(row: SubBenchmark) =>
              `${row.naicsCode ?? ''}-${row.agencyName ?? ''}-${row.subBusinessType ?? ''}`
            }
            sx={{ minHeight: 300 }}
          />
        </Box>
      )}

      {/* Sub-to-prime ratio chart */}
      {ratios && ratios.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Sub-to-Prime Ratio by NAICS
          </Typography>
          <BarChart
            xAxis={[{ scaleType: 'band', data: ratioChartData.naics, label: 'NAICS Code' }]}
            series={[
              {
                data: ratioChartData.avgRatios,
                label: 'Avg Sub Ratio (%)',
              },
            ]}
            height={350}
          />
        </Paper>
      )}
    </Box>
  );
}
