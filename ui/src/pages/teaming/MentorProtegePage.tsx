import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GridColDef } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Link from '@mui/material/Link';
import Pagination from '@mui/material/Pagination';
import TextField from '@mui/material/TextField';

import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { PageHeader } from '@/components/shared/PageHeader';
import { useMentorProtege } from '@/queries/useTeaming';
import { useDebounce } from '@/hooks/useDebounce';
import { formatCurrency, formatNumber } from '@/utils/formatters';
import type { MentorProtegePairDto } from '@/types/teaming';

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

function buildColumns(navigate: ReturnType<typeof useNavigate>): GridColDef<MentorProtegePairDto>[] {
  return [
    {
      field: 'protegeName',
      headerName: 'Protege',
      flex: 1,
      minWidth: 160,
      renderCell: (params) => {
        const name = params.value as string | null;
        const uei = params.row.protegeUei;
        if (!name) return '--';
        return (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/teaming/partner/${encodeURIComponent(uei)}`);
            }}
          >
            {name}
          </Link>
        );
      },
    },
    {
      field: 'protegeCertifications',
      headerName: 'Protege Certs',
      flex: 1,
      minWidth: 140,
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
      field: 'mentorName',
      headerName: 'Mentor',
      flex: 1,
      minWidth: 160,
      renderCell: (params) => {
        const name = params.value as string | null;
        const uei = params.row.mentorUei;
        if (!name) return '--';
        return (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/teaming/partner/${encodeURIComponent(uei)}`);
            }}
          >
            {name}
          </Link>
        );
      },
    },
    {
      field: 'sharedNaics',
      headerName: 'Shared NAICS',
      flex: 1,
      minWidth: 140,
      renderCell: (params) => {
        const codes = splitTags(params.value as string | null | undefined);
        if (codes.length === 0) return '--';
        return (
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', py: 0.5 }}>
            {codes.slice(0, 3).map((c) => (
              <Chip key={c} label={c} size="small" variant="outlined" />
            ))}
            {codes.length > 3 && (
              <Chip label={`+${codes.length - 3}`} size="small" color="default" />
            )}
          </Box>
        );
      },
    },
    {
      field: 'mentorContractCount',
      headerName: 'Mentor Contracts',
      width: 130,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatNumber(value),
    },
    {
      field: 'mentorTotalValue',
      headerName: 'Mentor Volume',
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

export default function MentorProtegePage() {
  const navigate = useNavigate();
  const [protegeUei, setProtegeUei] = useState('');
  const [naicsCode, setNaicsCode] = useState('');
  const [page, setPage] = useState(1);

  const debouncedProtege = useDebounce(protegeUei, 400);
  const debouncedNaics = useDebounce(naicsCode, 400);

  const params = useMemo(
    () => ({
      protegeUei: debouncedProtege || undefined,
      naicsCode: debouncedNaics || undefined,
      page,
      pageSize: 20,
    }),
    [debouncedProtege, debouncedNaics, page],
  );

  const { data, isLoading, isError, refetch } = useMentorProtege(params);

  const columns = useMemo(() => buildColumns(navigate), [navigate]);

  if (isError) {
    return (
      <Box>
        <PageHeader title="Mentor-Protege Matching" subtitle="Find mentor-protege partnership candidates" />
        <ErrorState
          title="Failed to load mentor-protege pairs"
          message="Could not retrieve data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title="Mentor-Protege Matching" subtitle="Find mentor-protege partnership candidates" />

      {/* Filter bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="Protege UEI"
          value={protegeUei}
          onChange={(e) => { setProtegeUei(e.target.value); setPage(1); }}
          sx={{ minWidth: 180 }}
        />
        <TextField
          size="small"
          label="NAICS Code"
          value={naicsCode}
          onChange={(e) => { setNaicsCode(e.target.value); setPage(1); }}
          sx={{ minWidth: 120 }}
        />
        {data && (
          <Chip
            label={`${data.totalCount} pair${data.totalCount !== 1 ? 's' : ''}`}
            color="primary"
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {isLoading && <LoadingState message="Searching mentor-protege pairs..." />}

      {!isLoading && (
        <>
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={false}
            getRowId={(row: MentorProtegePairDto) => `${row.protegeUei}-${row.mentorUei}-${row.sharedNaics}`}
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
