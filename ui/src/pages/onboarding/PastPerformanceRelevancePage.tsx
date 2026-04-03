import { useState } from 'react';
import Box from '@mui/material/Box';
import TextField from '@mui/material/TextField';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined';
import CancelOutlined from '@mui/icons-material/CancelOutlined';
import type { GridColDef } from '@mui/x-data-grid';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { DataTable } from '@/components/shared/DataTable';
import { usePastPerformanceRelevance } from '@/queries/useOnboarding';
import { formatCurrency } from '@/utils/formatters';
import type { PastPerformanceRelevanceDto } from '@/types/onboarding';

function relevanceColor(score: number | null | undefined): 'success' | 'warning' | 'error' | 'default' {
  if (score == null) return 'default';
  if (score >= 70) return 'success';
  if (score >= 40) return 'warning';
  return 'error';
}

const columns: GridColDef[] = [
  {
    field: 'contractNumber',
    headerName: 'Contract #',
    width: 150,
    valueGetter: (_value, row) => row.contractNumber ?? '--',
  },
  {
    field: 'ppAgency',
    headerName: 'PP Agency',
    width: 140,
    valueGetter: (_value, row) => row.ppAgency ?? '--',
  },
  {
    field: 'ppNaics',
    headerName: 'PP NAICS',
    width: 100,
  },
  {
    field: 'ppValue',
    headerName: 'PP Value',
    width: 130,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => (
      <Typography variant="body2">
        {formatCurrency(params.value as number | null, true)}
      </Typography>
    ),
  },
  {
    field: 'relevanceScore',
    headerName: 'Relevance',
    width: 120,
    renderCell: (params) => {
      const score = params.value as number | null;
      if (score == null) return '--';
      return (
        <Chip
          label={`${score.toFixed(0)}%`}
          size="small"
          color={relevanceColor(score)}
        />
      );
    },
  },
  {
    field: 'naicsMatch',
    headerName: 'NAICS Match',
    width: 110,
    align: 'center',
    headerAlign: 'center',
    renderCell: (params) =>
      params.value ? (
        <CheckCircleOutlined color="success" fontSize="small" />
      ) : (
        <CancelOutlined color="disabled" fontSize="small" />
      ),
  },
  {
    field: 'agencyMatch',
    headerName: 'Agency Match',
    width: 120,
    align: 'center',
    headerAlign: 'center',
    renderCell: (params) =>
      params.value ? (
        <CheckCircleOutlined color="success" fontSize="small" />
      ) : (
        <CancelOutlined color="disabled" fontSize="small" />
      ),
  },
  {
    field: 'valueSimilarity',
    headerName: 'Value Sim.',
    width: 110,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => {
      const val = params.value as number | null;
      return val != null ? `${val.toFixed(0)}%` : '--';
    },
  },
  {
    field: 'yearsSinceCompletion',
    headerName: 'Years Ago',
    width: 100,
    align: 'right',
    headerAlign: 'right',
    renderCell: (params) => {
      const val = params.value as number | null;
      return val != null ? val.toFixed(1) : '--';
    },
  },
  {
    field: 'opportunityTitle',
    headerName: 'Opportunity',
    flex: 1,
    minWidth: 180,
    valueGetter: (_value, row) => row.opportunityTitle ?? row.noticeId,
  },
];

export default function PastPerformanceRelevancePage() {
  const [noticeId, setNoticeId] = useState('');
  const filterNoticeId = noticeId.trim() || undefined;
  const { data: records, isLoading, isError, refetch } = usePastPerformanceRelevance(filterNoticeId);

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader
        title="Past Performance Relevance"
        subtitle="Rank past performance records by relevance to opportunities"
      />

      <Box sx={{ mb: 3 }}>
        <TextField
          label="Filter by Notice ID (optional)"
          value={noticeId}
          onChange={(e) => setNoticeId(e.target.value)}
          size="small"
          placeholder="e.g. abc123def456"
          sx={{ minWidth: 300 }}
        />
      </Box>

      {isLoading && <LoadingState />}
      {isError && <ErrorState onRetry={() => refetch()} />}

      {!isLoading && !isError && (!records || records.length === 0) && (
        <EmptyState
          title="No Past Performance Records"
          message={
            filterNoticeId
              ? `No past performance records found matching notice ID "${filterNoticeId}".`
              : 'No past performance records available. Add past performance records to your organization profile.'
          }
        />
      )}

      {!isLoading && !isError && records && records.length > 0 && (
        <DataTable
          columns={columns}
          rows={records}
          getRowId={(row: PastPerformanceRelevanceDto) => row.pastPerformanceId}
          sortModel={[{ field: 'relevanceScore', sort: 'desc' }]}
        />
      )}
    </Box>
  );
}
