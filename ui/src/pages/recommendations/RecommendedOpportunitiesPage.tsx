import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useSnackbar } from 'notistack';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import VisibilityIcon from '@mui/icons-material/Visibility';
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
import TextField from '@mui/material/TextField';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';

import { AgencyLink } from '@/components/shared/AgencyLink';
import { PageHeader } from '@/components/shared/PageHeader';
import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import PWinGauge from '@/components/shared/PWinGauge';
import { getRecommendedOpportunities } from '@/api/opportunities';
import { queryKeys } from '@/queries/queryKeys';
import { useIgnoreOpportunity, useUnignoreOpportunity, useIgnoredOpportunityIds } from '@/queries/useOpportunities';
import { formatCurrency } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import { useLocalStorage } from '@/hooks/useLocalStorage';
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
  ignoredSet: Set<string>,
  onIgnoreToggle: (noticeId: string, isIgnored: boolean) => void,
  ignoreDisabled: boolean,
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
      renderCell: (params) => params.row.departmentName ? <AgencyLink name={params.row.departmentName} agencyCode={params.row.contractingOfficeId ?? undefined} fhOrgId={params.row.fhOrgId} /> : '--',
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
      field: 'oqScore',
      headerName: 'OQS',
      width: 110,
      align: 'center',
      headerAlign: 'center',
      description: 'Opportunity Quality Score — rates how well this opportunity matches your profile based on weighted factors.',
      renderCell: (params) => {
        const row = params.row;
        const chip = scoreChip(row.oqScore);
        const content = (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {row.oqScore == null || !row.oqScoreFactors || row.oqScoreFactors.length === 0
              ? chip
              : (() => {
                  const lines = row.oqScoreFactors.map(
                    (f) => `${f.name.padEnd(20)} ${f.score} (wt ${(f.weight * 100).toFixed(0)}%)`,
                  );
                  const tooltipText = `OQS: ${row.oqScore}\n${lines.join('\n')}`;
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
                })()}
            {row.confidence && (
              <Chip
                label={row.confidence[0]}
                size="small"
                variant="outlined"
                color={row.confidence === 'High' ? 'success' : row.confidence === 'Medium' ? 'warning' : 'error'}
                sx={{ minWidth: 24, height: 20, '& .MuiChip-label': { px: 0.5, fontSize: '0.7rem' } }}
              />
            )}
          </Box>
        );
        return content;
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
    {
      field: 'actions',
      headerName: '',
      width: 60,
      sortable: false,
      renderCell: (params) => {
        const isIgnored = ignoredSet.has(params.row.noticeId);
        return (
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              onIgnoreToggle(params.row.noticeId, isIgnored);
            }}
            disabled={ignoreDisabled}
            title={isIgnored ? 'Un-ignore' : 'Ignore'}
            color={isIgnored ? 'warning' : 'default'}
          >
            {isIgnored ? <VisibilityIcon fontSize="small" /> : <VisibilityOffIcon fontSize="small" />}
          </IconButton>
        );
      },
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
  actions: 'sm',
};

export default function RecommendedOpportunitiesPage() {
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const [limit, setLimit] = useLocalStorage('recommended.limit', 25);
  const [savedPageSize, setSavedPageSize] = useLocalStorage('recommended.pageSize', 25);
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({ page: 0, pageSize: savedPageSize });
  const [keyword, setKeyword] = useState('');
  const [naicsFilter, setNaicsFilter] = useState('');
  const [setAsideFilter, setSetAsideFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const columnVisibility = useResponsiveColumns(RESPONSIVE_COLUMNS);

  const ignoreMutation = useIgnoreOpportunity();
  const unignoreMutation = useUnignoreOpportunity();
  const { data: ignoredIds } = useIgnoredOpportunityIds();
  const ignoredSet = useMemo(() => new Set(ignoredIds ?? []), [ignoredIds]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.opportunities.recommended(limit),
    queryFn: () => getRecommendedOpportunities(limit),
    staleTime: 5 * 60 * 1000,
  });

  // Client-side filters
  const filteredData = useMemo(() => {
    if (!data) return [];
    let result = data;
    if (keyword) {
      const kw = keyword.toLowerCase();
      result = result.filter(
        (r) => r.title?.toLowerCase().includes(kw) || r.solicitationNumber?.toLowerCase().includes(kw),
      );
    }
    if (naicsFilter) {
      result = result.filter((r) => r.naicsCode?.startsWith(naicsFilter));
    }
    if (setAsideFilter) {
      result = result.filter((r) => r.setAsideDescription === setAsideFilter);
    }
    if (typeFilter) {
      result = result.filter((r) => r.noticeType === typeFilter);
    }
    return result;
  }, [data, keyword, naicsFilter, setAsideFilter, typeFilter]);

  const setAsideOptions = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.map((r) => r.setAsideDescription).filter(Boolean))].sort() as string[];
  }, [data]);

  const typeOptions = useMemo(() => {
    if (!data) return [];
    return [...new Set(data.map((r) => r.noticeType).filter(Boolean))].sort() as string[];
  }, [data]);

  const hasActiveFilters = keyword !== '' || naicsFilter !== '' || setAsideFilter !== '' || typeFilter !== '';

  // Reset pagination when filters change
  useEffect(() => {
    setPaginationModel((prev) => (prev.page === 0 ? prev : { ...prev, page: 0 }));
  }, [keyword, naicsFilter, setAsideFilter, typeFilter]);

  // Extract noticeIds for the current visible page
  const currentPageNoticeIds = useMemo(() => {
    if (!filteredData.length) return [];
    const start = paginationModel.page * paginationModel.pageSize;
    const end = start + paginationModel.pageSize;
    return filteredData.slice(start, end).map((row) => row.noticeId);
  }, [filteredData, paginationModel]);

  const { pwinMap, isLoading: pwinLoading } = useBatchPWin(currentPageNoticeIds);

  const handleIgnoreToggle = useCallback(
    (noticeId: string, isIgnored: boolean) => {
      if (isIgnored) {
        unignoreMutation.mutate(noticeId, {
          onSuccess: () => enqueueSnackbar('Opportunity restored', { variant: 'info' }),
          onError: () => enqueueSnackbar('Failed to restore opportunity', { variant: 'error' }),
        });
      } else {
        ignoreMutation.mutate(
          { noticeId },
          {
            onSuccess: () => enqueueSnackbar('Opportunity ignored', { variant: 'info' }),
            onError: () => enqueueSnackbar('Failed to ignore opportunity', { variant: 'error' }),
          },
        );
      }
    },
    [ignoreMutation, unignoreMutation, enqueueSnackbar],
  );

  const columns = useMemo(
    () => buildColumns(pwinMap, pwinLoading, ignoredSet, handleIgnoreToggle, ignoreMutation.isPending || unignoreMutation.isPending),
    [pwinMap, pwinLoading, ignoredSet, handleIgnoreToggle, ignoreMutation.isPending, unignoreMutation.isPending],
  );

  const handleLimitChange = useCallback((e: SelectChangeEvent<number>) => {
    setLimit(Number(e.target.value));
  }, []);

  const handleRowClick = useCallback(
    (params: GridRowParams<RecommendedOpportunityDto>) => {
      const row = params.row;
      navigate(`/opportunities/${encodeURIComponent(row.noticeId)}`, {
        state: {
          oqScore: row.oqScore,
          oqScoreCategory: row.oqScoreCategory,
          oqScoreFactors: row.oqScoreFactors,
          confidence: row.confidence,
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

        <TextField
          size="small"
          label="Search"
          placeholder="Title or solicitation..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          sx={{ minWidth: 200 }}
        />
        <TextField
          size="small"
          label="NAICS"
          value={naicsFilter}
          onChange={(e) => setNaicsFilter(e.target.value)}
          sx={{ width: 100 }}
        />
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel id="set-aside-label">Set-Aside</InputLabel>
          <Select
            labelId="set-aside-label"
            value={setAsideFilter}
            label="Set-Aside"
            onChange={(e) => setSetAsideFilter(e.target.value)}
          >
            <MenuItem value="">All</MenuItem>
            {setAsideOptions.map((sa) => (
              <MenuItem key={sa} value={sa}>
                {sa}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel id="type-label">Type</InputLabel>
          <Select
            labelId="type-label"
            value={typeFilter}
            label="Type"
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <MenuItem value="">All</MenuItem>
            {typeOptions.map((t) => (
              <MenuItem key={t} value={t}>
                {t}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {data && (
          <Chip
            label={
              hasActiveFilters
                ? `${filteredData.length} of ${data.length} matches`
                : `${data.length} match${data.length !== 1 ? 'es' : ''}`
            }
            color="primary"
            size="small"
            variant="outlined"
          />
        )}
      </Box>

      {isLoading && <LoadingState message="Loading recommendations..." />}

      {!isLoading && data && data.length === 0 && !hasActiveFilters && (
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

      {!isLoading && data && (data.length > 0 || hasActiveFilters) && (
        <DataTable
          columns={columns}
          rows={filteredData}
          loading={false}
          paginationModel={paginationModel}
          onPaginationModelChange={(m) => { setPaginationModel(m); if (m.pageSize !== paginationModel.pageSize) setSavedPageSize(m.pageSize); }}
          onRowClick={handleRowClick}
          getRowId={(row: RecommendedOpportunityDto) => row.noticeId}
          columnVisibilityModel={columnVisibility}
          sx={{ minHeight: 400 }}
        />
      )}
    </Box>
  );
}
