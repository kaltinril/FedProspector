import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GridColDef, GridRowParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import MenuItem from '@mui/material/MenuItem';
import Pagination from '@mui/material/Pagination';
import TextField from '@mui/material/TextField';

import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { PageHeader } from '@/components/shared/PageHeader';
import { usePartnerSearch } from '@/queries/useTeaming';
import { useDebounce } from '@/hooks/useDebounce';
import { formatCurrency, formatNumber } from '@/utils/formatters';
import type { PartnerSearchResultDto } from '@/types/teaming';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CERTIFICATION_OPTIONS = [
  { value: '', label: 'All Certifications' },
  { value: '8(a)', label: '8(a)' },
  { value: 'WOSB', label: 'WOSB' },
  { value: 'EDWOSB', label: 'EDWOSB' },
  { value: 'HUBZone', label: 'HUBZone' },
  { value: 'SDVOSB', label: 'SDVOSB' },
];

const US_STATES = [
  '', 'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL',
  'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
  'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH',
  'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'PR',
  'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV',
  'WI', 'WY',
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function splitTags(raw: string | null | undefined): string[] {
  if (!raw) return [];
  return raw
    .split(/[,;|]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

function buildColumns(): GridColDef<PartnerSearchResultDto>[] {
  return [
    {
      field: 'legalBusinessName',
      headerName: 'Company Name',
      flex: 1.5,
      minWidth: 200,
      renderCell: (params) => {
        const name = params.value as string | null | undefined;
        return name ?? '--';
      },
    },
    {
      field: 'state',
      headerName: 'State',
      width: 80,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'naicsCodes',
      headerName: 'NAICS',
      flex: 1,
      minWidth: 160,
      renderCell: (params) => {
        const codes = splitTags(params.value as string | null | undefined);
        if (codes.length === 0) return '--';
        return (
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', py: 0.5 }}>
            {codes.slice(0, 4).map((c) => (
              <Chip key={c} label={c} size="small" variant="outlined" />
            ))}
            {codes.length > 4 && (
              <Chip label={`+${codes.length - 4}`} size="small" color="default" />
            )}
          </Box>
        );
      },
    },
    {
      field: 'certifications',
      headerName: 'Certifications',
      flex: 1,
      minWidth: 160,
      renderCell: (params) => {
        const certs = splitTags(params.value as string | null | undefined);
        if (certs.length === 0) return '--';
        return (
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', py: 0.5 }}>
            {certs.map((c) => (
              <Chip key={c} label={c} size="small" color="primary" variant="outlined" />
            ))}
          </Box>
        );
      },
    },
    {
      field: 'contractCount',
      headerName: 'Contracts',
      width: 100,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatNumber(value),
    },
    {
      field: 'totalContractValue',
      headerName: 'Total Value',
      width: 130,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value, true),
    },
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PartnerSearchPage() {
  const navigate = useNavigate();
  const [naicsCode, setNaicsCode] = useState('');
  const [state, setState] = useState('');
  const [certification, setCertification] = useState('');
  const [agencyCode, setAgencyCode] = useState('');
  const [page, setPage] = useState(1);

  const debouncedNaics = useDebounce(naicsCode, 400);
  const debouncedAgency = useDebounce(agencyCode, 400);

  const params = useMemo(
    () => ({
      naicsCode: debouncedNaics || undefined,
      state: state || undefined,
      certification: certification || undefined,
      agencyCode: debouncedAgency || undefined,
      page,
      pageSize: 20,
    }),
    [debouncedNaics, state, certification, debouncedAgency, page],
  );

  const { data, isLoading, isError, refetch } = usePartnerSearch(params);

  const columns = useMemo(() => buildColumns(), []);

  const handleRowClick = useCallback(
    (rowParams: GridRowParams<PartnerSearchResultDto>) => {
      navigate(`/teaming/partner/${encodeURIComponent(rowParams.row.ueiSam)}`);
    },
    [navigate],
  );

  if (isError) {
    return (
      <Box>
        <PageHeader title="Partner Search" subtitle="Find potential teaming partners" />
        <ErrorState
          title="Failed to load partners"
          message="Could not retrieve partner data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title="Partner Search" subtitle="Find potential teaming partners" />

      {/* Filter bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="NAICS Code"
          value={naicsCode}
          onChange={(e) => { setNaicsCode(e.target.value); setPage(1); }}
          sx={{ minWidth: 120 }}
        />
        <TextField
          size="small"
          label="State"
          select
          value={state}
          onChange={(e) => { setState(e.target.value); setPage(1); }}
          sx={{ minWidth: 100 }}
        >
          <MenuItem value="">All States</MenuItem>
          {US_STATES.filter(Boolean).map((s) => (
            <MenuItem key={s} value={s}>{s}</MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="Certification"
          select
          value={certification}
          onChange={(e) => { setCertification(e.target.value); setPage(1); }}
          sx={{ minWidth: 160 }}
        >
          {CERTIFICATION_OPTIONS.map((o) => (
            <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="Agency"
          value={agencyCode}
          onChange={(e) => { setAgencyCode(e.target.value); setPage(1); }}
          sx={{ minWidth: 180 }}
        />
        {data && (
          <Chip
            label={`${data.totalCount} partner${data.totalCount !== 1 ? 's' : ''}`}
            color="primary"
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {isLoading && <LoadingState message="Searching partners..." />}

      {!isLoading && (
        <>
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={false}
            onRowClick={handleRowClick}
            getRowId={(row: PartnerSearchResultDto) => row.ueiSam}
            sx={{ minHeight: 400 }}
          />
          {data && data.totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
              <Pagination
                count={data.totalPages}
                page={data.page}
                onChange={(_e, p) => setPage(p)}
                color="primary"
              />
            </Box>
          )}
        </>
      )}
    </Box>
  );
}
