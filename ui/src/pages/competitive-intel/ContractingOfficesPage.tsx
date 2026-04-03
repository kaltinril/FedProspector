import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GridColDef, GridRowParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Link from '@mui/material/Link';
import Pagination from '@mui/material/Pagination';
import TextField from '@mui/material/TextField';

import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { PageHeader } from '@/components/shared/PageHeader';
import { useOfficeSearch } from '@/queries/useCompetitiveIntel';
import { useDebounce } from '@/hooks/useDebounce';
import { formatCurrency, formatPercent } from '@/utils/formatters';
import type { ContractingOfficeProfileDto } from '@/types/competitiveIntel';

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

function buildColumns(navigate: ReturnType<typeof useNavigate>): GridColDef<ContractingOfficeProfileDto>[] {
  return [
    {
      field: 'contractingOfficeName',
      headerName: 'Office',
      flex: 1.5,
      minWidth: 200,
      renderCell: (params) => {
        const code = params.row.contractingOfficeId;
        return (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/competitive-intel/offices/${encodeURIComponent(code)}`);
            }}
          >
            {params.value ?? code}
          </Link>
        );
      },
    },
    {
      field: 'agencyName',
      headerName: 'Agency',
      flex: 1,
      minWidth: 160,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'totalAwards',
      headerName: 'Awards',
      width: 100,
      align: 'right',
      headerAlign: 'right',
    },
    {
      field: 'totalObligated',
      headerName: 'Total Obligated',
      width: 140,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value, true),
    },
    {
      field: 'avgAwardValue',
      headerName: 'Avg Award',
      width: 130,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value, true),
    },
    {
      field: 'smallBusinessPct',
      headerName: 'SB %',
      width: 80,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatPercent(value),
    },
    {
      field: 'fullCompetitionPct',
      headerName: 'Full Comp %',
      width: 110,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatPercent(value),
    },
    {
      field: 'soleSourcePct',
      headerName: 'Sole Source %',
      width: 110,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatPercent(value),
    },
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ContractingOfficesPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [agencyCode, setAgencyCode] = useState('');
  const [page, setPage] = useState(1);

  const debouncedSearch = useDebounce(search, 400);
  const debouncedAgency = useDebounce(agencyCode, 400);

  const params = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      agencyCode: debouncedAgency || undefined,
      page,
      pageSize: 20,
    }),
    [debouncedSearch, debouncedAgency, page],
  );

  const { data, isLoading, isError, refetch } = useOfficeSearch(params);
  const columns = useMemo(() => buildColumns(navigate), [navigate]);

  const handleRowClick = useCallback(
    (rowParams: GridRowParams<ContractingOfficeProfileDto>) => {
      navigate(`/competitive-intel/offices/${encodeURIComponent(rowParams.row.contractingOfficeId)}`);
    },
    [navigate],
  );

  if (isError) {
    return (
      <Box>
        <PageHeader title="Contracting Offices" subtitle="Browse and analyze contracting offices" />
        <ErrorState
          title="Failed to load offices"
          message="Could not retrieve office data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title="Contracting Offices" subtitle="Browse and analyze contracting offices" />

      {/* Filter bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="Search offices"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          sx={{ minWidth: 220 }}
        />
        <TextField
          size="small"
          label="Agency"
          value={agencyCode}
          onChange={(e) => { setAgencyCode(e.target.value); setPage(1); }}
          sx={{ minWidth: 180 }}
        />
        {data && (
          <Chip
            label={`${data.totalCount} office${data.totalCount !== 1 ? 's' : ''}`}
            color="primary"
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {isLoading && <LoadingState message="Loading offices..." />}

      {!isLoading && (
        <>
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={false}
            onRowClick={handleRowClick}
            getRowId={(row: ContractingOfficeProfileDto) => row.contractingOfficeId}
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
