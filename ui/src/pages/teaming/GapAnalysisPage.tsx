import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GridColDef, GridRowParams } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { PageHeader } from '@/components/shared/PageHeader';
import { useGapAnalysis } from '@/queries/useTeaming';
import { useDebounce } from '@/hooks/useDebounce';
import { formatCurrency, formatNumber } from '@/utils/formatters';
import type { PartnerSearchResultDto } from '@/types/teaming';

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
// Columns for gap-filling partners
// ---------------------------------------------------------------------------

function buildPartnerColumns(): GridColDef<PartnerSearchResultDto>[] {
  return [
    {
      field: 'legalBusinessName',
      headerName: 'Company Name',
      flex: 1.5,
      minWidth: 200,
      valueFormatter: (value: string | null | undefined) => value ?? '--',
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

export default function GapAnalysisPage() {
  const navigate = useNavigate();
  const [naicsCode, setNaicsCode] = useState('');

  const debouncedNaics = useDebounce(naicsCode, 400);

  const { data, isLoading, isError, refetch } = useGapAnalysis(debouncedNaics || undefined);

  const columns = useMemo(() => buildPartnerColumns(), []);

  const handleRowClick = (rowParams: GridRowParams<PartnerSearchResultDto>) => {
    navigate(`/teaming/partner/${encodeURIComponent(rowParams.row.ueiSam)}`);
  };

  if (isError) {
    return (
      <Box>
        <PageHeader title="Capability Gap Analysis" subtitle="Identify gaps and find partners to fill them" />
        <ErrorState
          title="Failed to load gap analysis"
          message="Could not retrieve analysis data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader title="Capability Gap Analysis" subtitle="Identify gaps and find partners to fill them" />
      {/* Filter */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <TextField
          size="small"
          label="NAICS Code"
          value={naicsCode}
          onChange={(e) => setNaicsCode(e.target.value)}
          sx={{ minWidth: 160 }}
          placeholder="Filter by NAICS..."
        />
      </Box>
      {isLoading && <LoadingState message="Analyzing capability gaps..." />}
      {!isLoading && data && (
        <>
          {/* Your organization's NAICS codes */}
          <Card variant="outlined" sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                Your Organization NAICS Codes
              </Typography>
              {data.orgNaicsCodes.length > 0 ? (
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  {data.orgNaicsCodes.map((code) => (
                    <Chip key={code} label={code} size="small" color="success" variant="outlined" />
                  ))}
                </Box>
              ) : (
                <Typography variant="body2" sx={{
                  color: "text.secondary"
                }}>
                  No NAICS codes configured for your organization. Visit Organization settings to add them.
                </Typography>
              )}
            </CardContent>
          </Card>

          <Divider sx={{ mb: 3 }} />

          {/* Gap-filling partners */}
          <Typography variant="h6" gutterBottom>
            Suggested Partners to Fill Gaps
          </Typography>
          <Typography
            variant="body2"
            sx={{
              color: "text.secondary",
              mb: 2
            }}>
            These partners have capabilities in NAICS codes where your organization lacks experience.
          </Typography>

          {data.gapFillingPartners.length === 0 ? (
            <Card variant="outlined">
              <CardContent>
                <Typography variant="body2" sx={{
                  color: "text.secondary"
                }}>
                  No gap-filling partners found. Try adjusting your NAICS filter or adding more NAICS codes to your organization profile.
                </Typography>
              </CardContent>
            </Card>
          ) : (
            <>
              <Chip
                label={`${data.gapFillingPartners.length} partner${data.gapFillingPartners.length !== 1 ? 's' : ''} found`}
                color="primary"
                size="small"
                variant="outlined"
                sx={{ mb: 2 }}
              />
              <DataTable
                columns={columns}
                rows={data.gapFillingPartners}
                loading={false}
                onRowClick={handleRowClick}
                getRowId={(row: PartnerSearchResultDto) => row.ueiSam}
                sx={{ minHeight: 300 }}
              />
            </>
          )}
        </>
      )}
    </Box>
  );
}
