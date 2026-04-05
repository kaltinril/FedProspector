import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { GridColDef } from '@mui/x-data-grid';
import Autocomplete, { createFilterOptions } from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';

import { PageHeader } from '@/components/shared/PageHeader';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { getScaAreaRates, getScaOccupations } from '@/api/pricing';
import { queryKeys } from '@/queries/queryKeys';
import type { ScaAreaRateDto } from '@/types/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const US_STATES = [
  '', 'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL',
  'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
  'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH',
  'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'PR',
  'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'VI', 'WA',
  'WV', 'WI', 'WY',
];

function formatCurrency(value: number | null | undefined): string {
  if (value == null) return '--';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '--';
  return new Date(value).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

const columns: GridColDef<ScaAreaRateDto>[] = [
  { field: 'state', headerName: 'State', width: 80 },
  { field: 'county', headerName: 'County', width: 150 },
  { field: 'areaName', headerName: 'Area Name', flex: 1, minWidth: 200 },
  { field: 'occupationCode', headerName: 'Occ Code', width: 100 },
  { field: 'occupationTitle', headerName: 'Occupation', flex: 1, minWidth: 200 },
  {
    field: 'hourlyRate',
    headerName: 'Hourly Rate',
    width: 120,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => (
      <Typography variant="body2" fontWeight={500}>
        {formatCurrency(params.value as number)}
      </Typography>
    ),
  },
  {
    field: 'fringe',
    headerName: 'Fringe',
    width: 110,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => (
      <Typography variant="body2">
        {formatCurrency(params.value as number)}
      </Typography>
    ),
  },
  {
    field: 'fullCost',
    headerName: 'Full Cost',
    width: 120,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => (
      <Typography variant="body2" fontWeight={600}>
        {formatCurrency(params.value as number)}
      </Typography>
    ),
  },
  {
    field: 'wdNumber',
    headerName: 'WD Number',
    width: 140,
    renderCell: (params) => {
      const wd = params.value as string | null;
      const rev = (params.row as ScaAreaRateDto).revision;
      if (!wd) return '--';
      const url = `https://sam.gov/wage-determination/${wd}/${rev ?? ''}`;
      return (
        <a href={url} target="_blank" rel="noopener noreferrer" style={{ color: '#90caf9' }}>
          {wd}
        </a>
      );
    },
  },
  { field: 'revision', headerName: 'Rev', width: 70, align: 'right', headerAlign: 'right' },
  {
    field: 'effectiveDate',
    headerName: 'Effective Date',
    width: 140,
    renderCell: (params) => formatDate(params.value as string | null),
  },
];

// ---------------------------------------------------------------------------
// Autocomplete filter — matches any part of the string
// ---------------------------------------------------------------------------

const occupationFilterOptions = createFilterOptions<string>({
  matchFrom: 'any',
  stringify: (option) => option,
});

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ScaGeographicPage() {
  // Filters
  const [occupationTitle, setOccupationTitle] = useState<string | null>(null);
  const [state, setState] = useState('');
  const [county, setCounty] = useState('');
  const [wdNumber, setWdNumber] = useState('');
  const [areaName, setAreaName] = useState('');

  // Committed search params (sent to API on Search click, or empty = load all)
  const [searchParams, setSearchParams] = useState<Record<string, string | undefined>>({});
  const [hasSearched, setHasSearched] = useState(true); // auto-load on mount

  // Occupation list for autocomplete
  const { data: occupationOptions = [] } = useQuery({
    queryKey: queryKeys.pricing.scaOccupations(),
    queryFn: getScaOccupations,
    staleTime: 30 * 60 * 1000, // 30 minutes — list rarely changes
  });

  const queryParams = useMemo(() => {
    const p: Record<string, string | undefined> = { ...searchParams };
    return p;
  }, [searchParams]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.pricing.scaAreaRates(queryParams),
    queryFn: () => getScaAreaRates(queryParams as Parameters<typeof getScaAreaRates>[0]),
    enabled: hasSearched,
    staleTime: 5 * 60 * 1000,
  });

  const handleSearch = useCallback(() => {
    const p: Record<string, string | undefined> = {};
    if (occupationTitle) p.occupationTitle = occupationTitle;
    if (state) p.state = state;
    if (county.trim()) p.county = county.trim();
    if (wdNumber.trim()) p.wdNumber = wdNumber.trim();
    if (areaName.trim()) p.areaName = areaName.trim();
    setSearchParams(p);
    setHasSearched(true);
  }, [occupationTitle, state, county, wdNumber, areaName]);

  const handleClear = useCallback(() => {
    setOccupationTitle(null);
    setState('');
    setCounty('');
    setWdNumber('');
    setAreaName('');
    setSearchParams({});
  }, []);

  if (isError) {
    return (
      <Box>
        <PageHeader
          title="SCA Area Rates"
          subtitle="Service Contract Act wage determinations by geographic area"
        />
        <ErrorState
          title="Failed to load SCA rates"
          message="Could not retrieve area rate data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="SCA Area Rates"
        subtitle="Service Contract Act wage determinations by geographic area"
      />

      {/* Filter row */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Autocomplete
          size="small"
          options={occupationOptions}
          filterOptions={occupationFilterOptions}
          value={occupationTitle}
          onChange={(_e, newValue) => setOccupationTitle(newValue)}
          renderInput={(params) => (
            <TextField {...params} label="Occupation" placeholder="Search occupation title..." />
          )}
          sx={{ minWidth: 300 }}
        />

        <FormControl size="small" sx={{ minWidth: 100 }}>
          <InputLabel id="sca-state-label">State</InputLabel>
          <Select
            labelId="sca-state-label"
            value={state}
            label="State"
            onChange={(e: SelectChangeEvent) => setState(e.target.value)}
          >
            <MenuItem value="">All</MenuItem>
            {US_STATES.filter(Boolean).map((s) => (
              <MenuItem key={s} value={s}>{s}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <TextField
          size="small"
          label="WD Number"
          placeholder="e.g. 2015-4281"
          value={wdNumber}
          onChange={(e) => setWdNumber(e.target.value)}
          sx={{ width: 160 }}
        />

        <TextField
          size="small"
          label="Area Name"
          placeholder="Search area..."
          value={areaName}
          onChange={(e) => setAreaName(e.target.value)}
          sx={{ width: 200 }}
        />

        <TextField
          size="small"
          label="County"
          placeholder="Search county..."
          value={county}
          onChange={(e) => setCounty(e.target.value)}
          sx={{ width: 180 }}
        />

        <Button variant="contained" size="small" onClick={handleSearch}>
          Search
        </Button>

        <Button variant="outlined" size="small" onClick={handleClear}>
          Clear
        </Button>
      </Box>

      {isLoading && <LoadingState message="Loading SCA area rates..." />}

      {!isLoading && hasSearched && (
        <DataTable
          columns={columns}
          rows={data ?? []}
          loading={false}
          getRowId={(row: ScaAreaRateDto) => `${row.state}-${row.county ?? ''}-${row.areaName}-${row.occupationCode}-${row.wdNumber ?? ''}`}
          sx={{ minHeight: 400 }}
        />
      )}
    </Box>
  );
}
