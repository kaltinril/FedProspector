import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GridColDef, GridRowParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Link from '@mui/material/Link';
import Pagination from '@mui/material/Pagination';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { PageHeader } from '@/components/shared/PageHeader';
import { useRecompeteCandidates } from '@/queries/useCompetitiveIntel';
import { useDebounce } from '@/hooks/useDebounce';
import { formatCurrency } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import type { RecompeteCandidateDto } from '@/types/competitiveIntel';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type ChipColor = 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning';

function urgencyColor(daysUntilEnd: number | null | undefined): ChipColor {
  if (daysUntilEnd == null) return 'default';
  if (daysUntilEnd < 180) return 'error';
  if (daysUntilEnd < 365) return 'warning';
  return 'success';
}

function urgencyLabel(daysUntilEnd: number | null | undefined): string {
  if (daysUntilEnd == null) return '--';
  if (daysUntilEnd < 0) return 'Expired';
  const months = Math.round(daysUntilEnd / 30);
  return `${months}mo`;
}

function truncate(text: string | null | undefined, maxLen: number): string {
  if (!text) return '--';
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '...';
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

function buildColumns(navigate: ReturnType<typeof useNavigate>): GridColDef<RecompeteCandidateDto>[] {
  return [
    {
      field: 'piid',
      headerName: 'Contract ID',
      flex: 1,
      minWidth: 140,
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
      field: 'description',
      headerName: 'Description',
      flex: 1.5,
      minWidth: 180,
      valueFormatter: (value: string | null | undefined) => truncate(value, 60),
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
              navigate(`/competitive-intel/competitor/${encodeURIComponent(uei)}`);
            }}
          >
            {name}
          </Link>
        );
      },
    },
    {
      field: 'agencyName',
      headerName: 'Agency',
      flex: 1,
      minWidth: 140,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'naicsCode',
      headerName: 'NAICS',
      width: 90,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'contractValue',
      headerName: 'Value',
      width: 120,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value, true),
    },
    {
      field: 'currentEndDate',
      headerName: 'End Date',
      width: 120,
      valueFormatter: (value: string | null | undefined) => formatDate(value),
    },
    {
      field: 'daysUntilEnd',
      headerName: 'Time Left',
      width: 100,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => {
        const days = params.value as number | null | undefined;
        return (
          <Chip
            label={urgencyLabel(days)}
            size="small"
            color={urgencyColor(days)}
          />
        );
      },
    },
    {
      field: 'setAsideType',
      headerName: 'Set-Aside',
      width: 130,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'extentCompeted',
      headerName: 'Competition',
      width: 130,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'incumbentRegistrationStatus',
      headerName: 'Incumbent Status',
      width: 140,
      renderCell: (params) => {
        const status = params.value as string | null | undefined;
        if (!status) return '--';
        const color: ChipColor = status === 'Active' ? 'success' : 'error';
        return <Chip label={status} size="small" color={color} variant="outlined" />;
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RecompeteCandidatesPage() {
  const navigate = useNavigate();
  const [naicsCode, setNaicsCode] = useState('');
  const [agencyCode, setAgencyCode] = useState('');
  const [setAsideCode, setSetAsideCode] = useState('');
  const [page, setPage] = useState(1);

  const debouncedNaics = useDebounce(naicsCode, 400);
  const debouncedAgency = useDebounce(agencyCode, 400);
  const debouncedSetAside = useDebounce(setAsideCode, 400);

  const params = useMemo(
    () => ({
      naicsCode: debouncedNaics || undefined,
      agencyCode: debouncedAgency || undefined,
      setAsideCode: debouncedSetAside || undefined,
      page,
      pageSize: 20,
    }),
    [debouncedNaics, debouncedAgency, debouncedSetAside, page],
  );

  const { data, isLoading, isError, refetch } = useRecompeteCandidates(params);

  const columns = useMemo(() => buildColumns(navigate), [navigate]);

  const handleRowClick = useCallback(
    (rowParams: GridRowParams<RecompeteCandidateDto>) => {
      const uei = rowParams.row.vendorUei;
      if (uei) {
        navigate(`/competitive-intel/competitor/${encodeURIComponent(uei)}`);
      }
    },
    [navigate],
  );

  if (isError) {
    return (
      <Box>
        <PageHeader title="Re-compete Candidates" subtitle="Contracts approaching re-competition" />
        <ErrorState
          title="Failed to load re-compete candidates"
          message="Could not retrieve contract data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title="Re-compete Candidates" subtitle="Contracts approaching re-competition" />

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
          label="Agency"
          value={agencyCode}
          onChange={(e) => { setAgencyCode(e.target.value); setPage(1); }}
          sx={{ minWidth: 180 }}
        />
        <TextField
          size="small"
          label="Set-Aside"
          value={setAsideCode}
          onChange={(e) => { setSetAsideCode(e.target.value); setPage(1); }}
          sx={{ minWidth: 130 }}
        />
        {data && (
          <Chip
            label={`${data.totalCount} candidate${data.totalCount !== 1 ? 's' : ''}`}
            color="primary"
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {isLoading && <LoadingState message="Loading re-compete candidates..." />}

      {!isLoading && (
        <>
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={false}
            onRowClick={handleRowClick}
            getRowId={(row: RecompeteCandidateDto) => `${row.source}-${row.piid}`}
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
