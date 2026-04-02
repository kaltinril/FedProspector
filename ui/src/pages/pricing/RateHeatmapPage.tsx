import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { GridColDef } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import Typography from '@mui/material/Typography';

import { PageHeader } from '@/components/shared/PageHeader';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { getRateHeatmap } from '@/api/pricing';
import { queryKeys } from '@/queries/queryKeys';
import type { RateHeatmapCell } from '@/types/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CATEGORY_GROUPS = ['All', 'IT', 'Engineering', 'Professional', 'Administrative', 'Healthcare'];
const WORKSITES = ['All', 'Contractor Site', 'Customer Site', 'Both'];
const EDUCATION_LEVELS = ['All', 'High School', 'Associates', 'Bachelors', 'Masters', 'PhD'];

function formatRate(value: number | null | undefined): string {
  if (value == null) return '--';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value) + '/hr';
}

function rateColor(value: number, min: number, max: number): string {
  if (max === min) return 'inherit';
  const ratio = (value - min) / (max - min);
  if (ratio < 0.33) return '#4caf50'; // green
  if (ratio < 0.66) return '#ff9800'; // yellow/orange
  return '#f44336'; // red
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

function buildColumns(globalMin: number, globalMax: number): GridColDef<RateHeatmapCell>[] {
  const rateCellDef = (
    field: keyof RateHeatmapCell,
    headerName: string,
  ): GridColDef<RateHeatmapCell> => ({
    field,
    headerName,
    width: 120,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => {
      const val = params.value as number;
      return (
        <Typography
          variant="body2"
          sx={{ color: rateColor(val, globalMin, globalMax), fontWeight: 500 }}
        >
          {formatRate(val)}
        </Typography>
      );
    },
  });

  return [
    { field: 'canonicalName', headerName: 'Category', flex: 1.5, minWidth: 200 },
    { field: 'categoryGroup', headerName: 'Group', width: 130 },
    { field: 'worksite', headerName: 'Worksite', width: 140 },
    { field: 'educationLevel', headerName: 'Education', width: 120 },
    {
      field: 'rateCount',
      headerName: 'Count',
      width: 90,
      align: 'center',
      headerAlign: 'center',
    },
    rateCellDef('minRate', 'Min Rate'),
    rateCellDef('avgRate', 'Avg Rate'),
    rateCellDef('p25Rate', 'P25 Rate'),
    rateCellDef('medianRate', 'Median Rate'),
    rateCellDef('p75Rate', 'P75 Rate'),
    rateCellDef('maxRate', 'Max Rate'),
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RateHeatmapPage() {
  const [categoryGroup, setCategoryGroup] = useState('All');
  const [worksite, setWorksite] = useState('All');
  const [educationLevel, setEducationLevel] = useState('All');

  const params = useMemo(() => ({
    categoryGroup: categoryGroup === 'All' ? undefined : categoryGroup,
    worksite: worksite === 'All' ? undefined : worksite,
    educationLevel: educationLevel === 'All' ? undefined : educationLevel,
  }), [categoryGroup, worksite, educationLevel]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.pricing.heatmap(params),
    queryFn: () => getRateHeatmap(params),
    staleTime: 5 * 60 * 1000,
  });

  const { globalMin, globalMax } = useMemo(() => {
    if (!data?.length) return { globalMin: 0, globalMax: 1 };
    let min = Infinity;
    let max = -Infinity;
    for (const row of data) {
      if (row.minRate < min) min = row.minRate;
      if (row.maxRate > max) max = row.maxRate;
    }
    return { globalMin: min, globalMax: max };
  }, [data]);

  const columns = useMemo(() => buildColumns(globalMin, globalMax), [globalMin, globalMax]);

  if (isError) {
    return (
      <Box>
        <PageHeader title="Market Rate Heatmap" subtitle="Labor rate analysis across categories" />
        <ErrorState
          title="Failed to load rate data"
          message="Could not retrieve market rate information. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title="Market Rate Heatmap" subtitle="Labor rate analysis across categories" />

      {/* Filter bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel id="cat-group-label">Category Group</InputLabel>
          <Select
            labelId="cat-group-label"
            value={categoryGroup}
            label="Category Group"
            onChange={(e: SelectChangeEvent) => setCategoryGroup(e.target.value)}
          >
            {CATEGORY_GROUPS.map((g) => (
              <MenuItem key={g} value={g}>{g}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel id="worksite-label">Worksite</InputLabel>
          <Select
            labelId="worksite-label"
            value={worksite}
            label="Worksite"
            onChange={(e: SelectChangeEvent) => setWorksite(e.target.value)}
          >
            {WORKSITES.map((w) => (
              <MenuItem key={w} value={w}>{w}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel id="edu-label">Education Level</InputLabel>
          <Select
            labelId="edu-label"
            value={educationLevel}
            label="Education Level"
            onChange={(e: SelectChangeEvent) => setEducationLevel(e.target.value)}
          >
            {EDUCATION_LEVELS.map((e) => (
              <MenuItem key={e} value={e}>{e}</MenuItem>
            ))}
          </Select>
        </FormControl>

        {data && (
          <Chip
            label={`${data.length} rate${data.length !== 1 ? 's' : ''}`}
            color="primary"
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {isLoading && <LoadingState message="Loading market rates..." />}

      {!isLoading && (
        <DataTable
          columns={columns}
          rows={data ?? []}
          loading={false}
          getRowId={(row: RateHeatmapCell) => `${row.canonicalName}-${row.worksite ?? ''}-${row.educationLevel ?? ''}`}
          sx={{ minHeight: 400 }}
        />
      )}
    </Box>
  );
}
