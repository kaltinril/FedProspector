import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { GridColDef, GridPaginationModel, GridRowParams } from '@mui/x-data-grid';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import Skeleton from '@mui/material/Skeleton';
import Tooltip from '@mui/material/Tooltip';

import { AgencyLink } from '@/components/shared/AgencyLink';
import { PageHeader } from '@/components/shared/PageHeader';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import PWinGauge from '@/components/shared/PWinGauge';
import { getRecommendedOpportunities } from '@/api/opportunities';
import { queryKeys } from '@/queries/queryKeys';
import { formatCurrency } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import { useResponsiveColumns } from '@/hooks/useResponsiveColumns';
import type { ResponsiveColumnConfig } from '@/hooks/useResponsiveColumns';
import { useBatchPWin } from '@/hooks/useBatchPWin';
import type { BatchPWinEntry, RecommendedOpportunityDto } from '@/types/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type ChipColor = 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning';

function daysRemainingChip(days: number | null | undefined) {
  if (days == null) return <Chip label="--" size="small" color="default" />;
  let color: ChipColor = 'success';
  if (days < 7) color = 'error';
  else if (days < 14) color = 'warning';
  return <Chip label={`${days}d`} size="small" color={color} />;
}

function scoreChip(score: number | null | undefined) {
  if (score == null) return <Chip label="--" size="small" color="default" />;
  let color: ChipColor = 'error';
  if (score >= 70) color = 'success';
  else if (score >= 40) color = 'warning';
  return <Chip label={score} size="small" color={color} />;
}

function noticeTypeChip(noticeType: string | null | undefined) {
  if (!noticeType) return <Chip label="--" size="small" color="default" />;

  let label: string;
  let color: ChipColor;

  switch (noticeType) {
    case 'Combined Synopsis/Solicitation':
      label = 'Combined';
      color = 'primary';
      break;
    case 'Solicitation':
      label = 'Solicitation';
      color = 'primary';
      break;
    case 'Presolicitation':
      label = 'Presol';
      color = 'info';
      break;
    case 'Sources Sought':
      label = 'Sources Sought';
      color = 'warning';
      break;
    case 'Special Notice':
      label = 'Special';
      color = 'default';
      break;
    default:
      label = noticeType.length > 16 ? noticeType.slice(0, 14) + '...' : noticeType;
      color = 'default';
      break;
  }

  const chip = <Chip label={label} size="small" color={color} />;

  // Show full name in tooltip when the label is abbreviated
  if (label !== noticeType) {
    return (
      <Tooltip title={noticeType} arrow>
        {chip}
      </Tooltip>
    );
  }
  return chip;
}

function truncate(text: string | null | undefined, maxLen: number): string {
  if (!text) return '--';
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '...';
}

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

function buildColumns(
  pwinMap: Map<string, BatchPWinEntry>,
  pwinLoading: boolean,
): GridColDef<RecommendedOpportunityDto>[] {
  return [
    {
      field: 'title',
      headerName: 'Title',
      flex: 2,
      minWidth: 200,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'noticeType',
      headerName: 'Type',
      width: 140,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => noticeTypeChip(params.value as string | null | undefined),
      sortable: true,
    },
    {
      field: 'departmentName',
      headerName: 'Agency',
      flex: 1,
      minWidth: 140,
      renderCell: (params) => params.row.departmentName ? <AgencyLink name={params.row.departmentName} agencyCode={params.row.contractingOfficeId ?? undefined} /> : '--',
    },
    {
      field: 'naicsCode',
      headerName: 'NAICS',
      width: 90,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
    },
    {
      field: 'setAsideDescription',
      headerName: 'Set-Aside',
      flex: 0.8,
      minWidth: 120,
      valueFormatter: (value: string | null | undefined) => truncate(value, 30),
    },
    {
      field: 'awardAmount',
      headerName: 'Est. Value',
      width: 120,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value, true),
    },
    {
      field: 'responseDeadline',
      headerName: 'Deadline',
      width: 120,
      valueFormatter: (value: string | null | undefined) => formatDate(value),
    },
    {
      field: 'daysRemaining',
      headerName: 'Days Left',
      width: 100,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => daysRemainingChip(params.value as number | null | undefined),
    },
    {
      field: 'qScore',
      headerName: 'qScore',
      width: 90,
      align: 'center',
      headerAlign: 'center',
      description: 'Quick Score — rates how well this opportunity matches your profile based on set-aside, NAICS, timeline, and value.',
      renderCell: (params) => {
        const row = params.row;
        const chip = scoreChip(params.value as number | null | undefined);
        if (params.value == null || !row.qScoreFactors || row.qScoreFactors.length === 0) {
          return chip;
        }
        const lines = row.qScoreFactors.map(
          (f) => `${f.name.padEnd(20)} ${f.points}/${f.maxPoints}`,
        );
        const tooltipText = `qScore: ${params.value}\n${lines.join('\n')}`;
        return (
          <Tooltip
            title={
              <Box sx={{ whiteSpace: 'pre', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                {tooltipText}
              </Box>
            }
            arrow
          >
            {chip}
          </Tooltip>
        );
      },
    },
    {
      field: 'pWin',
      headerName: 'pWin',
      width: 80,
      align: 'center',
      headerAlign: 'center',
      sortable: false,
      renderCell: (params) => {
        const entry = pwinMap.get(params.row.noticeId);
        if (pwinLoading) {
          return <Skeleton variant="rounded" width={48} height={24} />;
        }
        if (entry) {
          return <PWinGauge score={entry.score} category={entry.category} variant="chip" />;
        }
        return '\u2014';
      },
    },
    {
      field: 'isRecompete',
      headerName: 'Recompete',
      width: 110,
      align: 'center',
      headerAlign: 'center',
      renderCell: (params) => {
        if (!params.value) return null;
        const incumbentName = params.row.incumbentName;
        const chip = <Chip label="Yes" size="small" color="info" />;
        if (incumbentName) {
          return (
            <Tooltip title={`Incumbent: ${incumbentName}`} arrow>
              {chip}
            </Tooltip>
          );
        }
        return chip;
      },
      sortable: false,
    },
  ];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const LIMIT_OPTIONS = [
  { value: 10, label: 'Top 10' },
  { value: 25, label: 'Top 25' },
  { value: 50, label: 'Top 50' },
];

const RESPONSIVE_COLUMNS: ResponsiveColumnConfig = {
  noticeType: 'md',
  departmentName: 'md',
  naicsCode: 'lg',
  setAsideDescription: 'md',
  awardAmount: 'md',
  pWin: 'lg',
};

export default function RecommendedOpportunitiesPage() {
  const navigate = useNavigate();
  const [limit, setLimit] = useState(25);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({ page: 0, pageSize: 25 });
  const columnVisibility = useResponsiveColumns(RESPONSIVE_COLUMNS);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.opportunities.recommended(limit),
    queryFn: () => getRecommendedOpportunities(limit),
    staleTime: 5 * 60 * 1000,
  });

  // Extract noticeIds for the current visible page
  const currentPageNoticeIds = useMemo(() => {
    if (!data) return [];
    const start = paginationModel.page * paginationModel.pageSize;
    const end = start + paginationModel.pageSize;
    return data.slice(start, end).map((row) => row.noticeId);
  }, [data, paginationModel]);

  const { pwinMap, isLoading: pwinLoading } = useBatchPWin(currentPageNoticeIds);

  const columns = useMemo(() => buildColumns(pwinMap, pwinLoading), [pwinMap, pwinLoading]);

  const handleLimitChange = useCallback((e: SelectChangeEvent<number>) => {
    setLimit(Number(e.target.value));
  }, []);

  const handleRowClick = useCallback(
    (params: GridRowParams<RecommendedOpportunityDto>) => {
      const row = params.row;
      navigate(`/opportunities/${encodeURIComponent(row.noticeId)}`, {
        state: {
          qScore: row.qScore,
          qScoreCategory: row.qScoreCategory,
          qScoreFactors: row.qScoreFactors,
        },
      });
    },
    [navigate],
  );

  if (isError) {
    return (
      <Box>
        <PageHeader
          title="Recommended Opportunities"
          subtitle="Personalized matches based on your organization profile"
        />
        <ErrorState
          title="Failed to load recommendations"
          message="Could not retrieve recommended opportunities. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="Recommended Opportunities"
        subtitle="Personalized matches based on your organization profile"
      />

      {/* Filter bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel id="limit-label">Show</InputLabel>
          <Select
            labelId="limit-label"
            value={limit}
            label="Show"
            onChange={handleLimitChange}
          >
            {LIMIT_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {data && (
          <Chip
            label={`${data.length} match${data.length !== 1 ? 'es' : ''}`}
            color="primary"
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {isLoading && <LoadingState message="Loading recommendations..." />}

      {!isLoading && data && data.length === 0 && (
        <Alert
          severity="info"
          sx={{ mb: 2 }}
          action={
            <Button color="inherit" size="small" onClick={() => navigate('/organization')}>
              Configure
            </Button>
          }
        >
          No recommendations found. Link your SAM.gov entity and configure your NAICS codes to get
          personalized matches.
        </Alert>
      )}

      {!isLoading && data && data.length > 0 && (
        <DataTable
          columns={columns}
          rows={data}
          loading={false}
          paginationModel={paginationModel}
          onPaginationModelChange={setPaginationModel}
          onRowClick={handleRowClick}
          getRowId={(row: RecommendedOpportunityDto) => row.noticeId}
          columnVisibilityModel={columnVisibility}
          sx={{ minHeight: 400 }}
        />
      )}
    </Box>
  );
}
