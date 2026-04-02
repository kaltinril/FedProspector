import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { GridColDef } from '@mui/x-data-grid';
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { LineChart } from '@mui/x-charts/LineChart';

import { PageHeader } from '@/components/shared/PageHeader';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { getCanonicalCategories, searchLaborCategories, getRateTrends, getEscalationForecast } from '@/api/pricing';
import { queryKeys } from '@/queries/queryKeys';
import { useDebounce } from '@/hooks/useDebounce';
import type { CanonicalCategory, RateTrend } from '@/types/api';

// ---------------------------------------------------------------------------
// Chart colors — shared between chart series and table columns
// ---------------------------------------------------------------------------

const COLORS = {
  avg: '#ff9800',       // orange/yellow — historical avg rate line (matches forecast)
  forecast: '#ff9800',  // orange/yellow — forecast line (same as avg for continuity)
  minRate: '#ef5350',   // red — min rate line + area bottom
  maxRate: '#42a5f5',   // light blue — max rate line + area top
  confLow: '#ef5350',   // red — confidence low
  confHigh: '#42a5f5',  // light blue — confidence high
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const YEAR_OPTIONS = [
  { value: 3, label: '3 years' },
  { value: 5, label: '5 years' },
  { value: 10, label: '10 years' },
];

const MIN_DATA_POINTS = 3;

function formatRate(value: number | null | undefined): string {
  if (value == null) return '--';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value) + '/hr';
}

// ---------------------------------------------------------------------------
// Columns — color-coded to match chart series
// ---------------------------------------------------------------------------

function buildTrendColumns(): GridColDef<RateTrend>[] {
  return [
    { field: 'year', headerName: 'Year', width: 80 },
    {
      field: 'avgRate',
      headerName: 'Avg Rate',
      width: 120,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number) => formatRate(value),
      renderCell: (params) => (
        <Typography variant="body2" sx={{ color: COLORS.avg, fontWeight: 500 }}>
          {formatRate(params.value as number)}
        </Typography>
      ),
    },
    {
      field: 'minRate',
      headerName: 'Min Rate',
      width: 120,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <Typography variant="body2" sx={{ color: COLORS.confLow }}>
          {formatRate(params.value as number)}
        </Typography>
      ),
    },
    {
      field: 'maxRate',
      headerName: 'Max Rate',
      width: 120,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <Typography variant="body2" sx={{ color: COLORS.confHigh }}>
          {formatRate(params.value as number)}
        </Typography>
      ),
    },
    {
      field: 'rateCount',
      headerName: 'Count',
      width: 90,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => {
        const count = params.value as number;
        const isLow = count < MIN_DATA_POINTS;
        return (
          <Typography
            variant="body2"
            sx={{
              color: isLow ? 'warning.main' : 'text.primary',
              fontWeight: isLow ? 600 : 400,
            }}
          >
            {count}{isLow ? '*' : ''}
          </Typography>
        );
      },
    },
    {
      field: 'yoyChangePct',
      headerName: 'YoY Change (Avg)',
      width: 140,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => {
        const val = params.value as number | undefined;
        if (val == null) return '--';
        const color = val > 0 ? 'error.main' : val < 0 ? 'success.main' : 'text.primary';
        const sign = val > 0 ? '+' : '';
        return (
          <Typography variant="body2" sx={{ color, fontWeight: 500 }}>
            {sign}{val.toFixed(1)}%
          </Typography>
        );
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function EscalationPage() {
  const [categorySearch, setCategorySearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<CanonicalCategory | null>(null);
  const [years, setYears] = useState(5);

  const debouncedSearch = useDebounce(categorySearch, 300);

  const { data: categories = [] } = useQuery({
    queryKey: debouncedSearch
      ? queryKeys.pricing.categorySearch(debouncedSearch)
      : queryKeys.pricing.categories(),
    queryFn: () => debouncedSearch
      ? searchLaborCategories(debouncedSearch)
      : getCanonicalCategories(),
    staleTime: 5 * 60 * 1000,
  });

  const canonicalId = selectedCategory?.id;

  const {
    data: trends,
    isLoading: trendsLoading,
    isError: trendsError,
    refetch: refetchTrends,
  } = useQuery({
    queryKey: queryKeys.pricing.rateTrends(canonicalId ?? 0, years),
    queryFn: () => getRateTrends(canonicalId!, years),
    enabled: canonicalId != null,
    staleTime: 5 * 60 * 1000,
  });

  const { data: forecast } = useQuery({
    queryKey: queryKeys.pricing.escalation(canonicalId ?? 0, years),
    queryFn: () => getEscalationForecast(canonicalId!, years),
    enabled: canonicalId != null,
    staleTime: 5 * 60 * 1000,
  });

  const trendColumns = useMemo(() => buildTrendColumns(), []);

  // Filter trends: flag years with too few data points
  const reliableTrends = useMemo(
    () => trends?.filter((t) => t.rateCount >= MIN_DATA_POINTS) ?? [],
    [trends],
  );

  // Chart data: merge historical + forecast, include min/max area
  const chartData = useMemo(() => {
    const allYears: number[] = [];
    const avgRates: (number | null)[] = [];
    const minRates: (number | null)[] = [];
    const maxRates: (number | null)[] = [];
    const forecastRates: (number | null)[] = [];
    const confLow: (number | null)[] = [];
    const confHigh: (number | null)[] = [];

    // Use reliable trends (min 3 data points) for the chart
    if (reliableTrends.length > 0) {
      for (const t of reliableTrends) {
        allYears.push(t.year);
        avgRates.push(t.avgRate);
        minRates.push(t.minRate);
        maxRates.push(t.maxRate);
        forecastRates.push(null);
        confLow.push(null);
        confHigh.push(null);
      }
    }
    if (forecast) {
      for (const f of forecast) {
        if (!allYears.includes(f.year)) {
          allYears.push(f.year);
          avgRates.push(null);
          minRates.push(null);
          maxRates.push(null);
        }
        const idx = allYears.indexOf(f.year);
        forecastRates[idx] = f.projectedRate;
        confLow[idx] = f.confidenceLow;
        confHigh[idx] = f.confidenceHigh;
      }
    }

    // Fill nulls for arrays to match length
    while (avgRates.length < allYears.length) avgRates.push(null);
    while (minRates.length < allYears.length) minRates.push(null);
    while (maxRates.length < allYears.length) maxRates.push(null);
    while (forecastRates.length < allYears.length) forecastRates.push(null);
    while (confLow.length < allYears.length) confLow.push(null);
    while (confHigh.length < allYears.length) confHigh.push(null);

    return { allYears, avgRates, minRates, maxRates, forecastRates, confLow, confHigh };
  }, [reliableTrends, forecast]);

  const hasLowCountYears = trends?.some((t) => t.rateCount < MIN_DATA_POINTS);

  return (
    <Box>
      <PageHeader
        title="Rate Escalation Forecast"
        subtitle="Historical trends and projected rate escalation"
      />

      {/* Filters */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap', alignItems: 'center' }}>
        <Autocomplete
          size="small"
          options={categories}
          getOptionLabel={(opt) => opt.name}
          value={selectedCategory}
          onChange={(_, val) => setSelectedCategory(val)}
          inputValue={categorySearch}
          onInputChange={(_, val) => setCategorySearch(val)}
          renderInput={(params) => (
            <TextField {...params} label="Labor Category" sx={{ minWidth: 280 }} />
          )}
          sx={{ minWidth: 280 }}
          isOptionEqualToValue={(opt, val) => opt.id === val.id}
        />

        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel id="years-label">Forecast Period</InputLabel>
          <Select
            labelId="years-label"
            value={years}
            label="Forecast Period"
            onChange={(e: SelectChangeEvent<number>) => setYears(Number(e.target.value))}
          >
            {YEAR_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))}
          </Select>
        </FormControl>

        {selectedCategory && (
          <Chip
            label={selectedCategory.group ?? ''}
            size="small"
            color="primary"
            variant="outlined"
          />
        )}
      </Box>

      {!selectedCategory && (
        <Typography color="text.secondary" sx={{ mt: 4, textAlign: 'center' }}>
          Select a labor category to view rate escalation data
        </Typography>
      )}

      {trendsLoading && <LoadingState message="Loading rate trends..." />}

      {trendsError && (
        <ErrorState
          title="Failed to load trends"
          message="Could not retrieve rate trend data."
          onRetry={() => refetchTrends()}
        />
      )}

      {/* Chart */}
      {selectedCategory && chartData.allYears.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Rate Trend & Forecast: {selectedCategory.name}
          </Typography>
          <LineChart
            xAxis={[{
              data: chartData.allYears,
              scaleType: 'point',
              label: 'Year',
            }]}
            series={[
              {
                data: chartData.maxRates,
                label: 'Max Rate',
                color: COLORS.confHigh,
                connectNulls: false,
                showMark: false,
                area: true,
              },
              {
                data: chartData.minRates,
                label: 'Min Rate',
                color: COLORS.confLow,
                connectNulls: false,
                showMark: false,
                area: true,
              },
              {
                data: chartData.avgRates,
                label: 'Historical Avg Rate',
                color: COLORS.avg,
                connectNulls: false,
              },
              {
                data: chartData.forecastRates,
                label: 'Forecast',
                color: COLORS.forecast,
                connectNulls: false,
              },
              {
                data: chartData.confLow,
                label: 'Confidence Low',
                color: COLORS.confLow,
                connectNulls: false,
                showMark: false,
              },
              {
                data: chartData.confHigh,
                label: 'Confidence High',
                color: COLORS.confHigh,
                connectNulls: false,
                showMark: false,
              },
            ]}
            height={400}
            sx={{
              '& .MuiAreaElement-root:nth-of-type(1)': { fill: 'rgba(66, 165, 245, 0.15)' },
              '& .MuiAreaElement-root:nth-of-type(2)': { fill: 'var(--mui-palette-background-default, #121212)' },
            }}
          />
        </Paper>
      )}

      {/* YoY Table */}
      {trends && trends.length > 0 && (
        <Box>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Year-over-Year Rate Changes
          </Typography>
          {hasLowCountYears && (
            <Typography variant="caption" color="warning.main" sx={{ mb: 1, display: 'block' }}>
              * Years with fewer than {MIN_DATA_POINTS} data points may not be statistically reliable.
              These years are excluded from the chart.
            </Typography>
          )}
          <DataTable
            columns={trendColumns}
            rows={trends}
            loading={false}
            getRowId={(row: RateTrend) => String(row.year)}
            sx={{ minHeight: 300 }}
          />
        </Box>
      )}
    </Box>
  );
}
