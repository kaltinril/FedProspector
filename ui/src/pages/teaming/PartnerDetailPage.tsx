import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { GridColDef } from '@mui/x-data-grid';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Link from '@mui/material/Link';
import Pagination from '@mui/material/Pagination';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';

import { DataTable } from '@/components/shared/DataTable';
import { ErrorState } from '@/components/shared/ErrorState';
import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import { LoadingState } from '@/components/shared/LoadingState';
import { PageHeader } from '@/components/shared/PageHeader';
import {
  usePartnerRisk,
  usePartnerRelationships,
  usePartnerNetwork,
} from '@/queries/useTeaming';
import { formatCurrency, formatNumber } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import type {
  PartnerRiskDto,
  PrimeSubRelationshipDto,
  TeamingNetworkNodeDto,
} from '@/types/teaming';

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

type ChipColor = 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning';

function riskChipColor(level: string): ChipColor {
  const upper = level.toUpperCase();
  if (upper === 'GREEN') return 'success';
  if (upper === 'YELLOW') return 'warning';
  if (upper === 'RED') return 'error';
  return 'default';
}

function riskChip(level: string) {
  return (
    <Chip
      label={level}
      size="small"
      color={riskChipColor(level)}
    />
  );
}

function formatPct(value: number | null | undefined): string {
  if (value == null) return '--';
  return `${value.toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// Tab: Capabilities
// ---------------------------------------------------------------------------

function CapabilitiesTab({ risk }: { risk: PartnerRiskDto }) {
  // We derive capabilities from what's available in the risk DTO
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Typography variant="subtitle1" gutterBottom>Certifications</Typography>
        <Typography variant="body2" color="text.secondary">
          {risk.certificationCount > 0
            ? `${risk.certificationCount} active certification(s)`
            : 'No certifications on record'}
        </Typography>
      </Box>
      <Divider />
      <Box>
        <Typography variant="subtitle1" gutterBottom>Business Profile</Typography>
        <KeyFactsGrid
          facts={[
            { label: 'Years in Business', value: risk.yearsInBusiness != null ? `${risk.yearsInBusiness.toFixed(1)} years` : '--' },
            { label: 'Total Contract Value', value: formatCurrency(risk.totalContractValue, true) },
            { label: 'Top Agency', value: risk.topAgencyName ?? '--' },
            { label: 'Customer Concentration', value: formatPct(risk.customerConcentrationPct) },
          ]}
          columns={2}
        />
      </Box>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Tab: Risk Assessment
// ---------------------------------------------------------------------------

function RiskTab({ risk }: { risk: PartnerRiskDto }) {
  const facts = [
    { label: 'Risk Level', value: riskChip(risk.riskLevel) },
    { label: 'Risk Summary', value: risk.riskSummary ?? '--', fullWidth: true },
    { label: 'Current Exclusion', value: risk.currentExclusionFlag ? <Chip label="EXCLUDED" size="small" color="error" /> : <Chip label="Clear" size="small" color="success" variant="outlined" /> },
    { label: 'Exclusion Count', value: formatNumber(risk.exclusionCount) },
    { label: 'Terminations for Cause', value: formatNumber(risk.terminationForCauseCount) },
    { label: 'Spending Trajectory', value: risk.spendingTrajectory ?? '--' },
    { label: 'Recent 2yr Value', value: formatCurrency(risk.recent2yrValue, true) },
    { label: 'Prior 2yr Value', value: formatCurrency(risk.prior2yrValue, true) },
    { label: 'Top Agency', value: risk.topAgencyName ?? '--' },
    { label: 'Customer Concentration', value: formatPct(risk.customerConcentrationPct) },
    { label: 'Certifications', value: formatNumber(risk.certificationCount) },
    { label: 'Years in Business', value: risk.yearsInBusiness != null ? `${risk.yearsInBusiness.toFixed(1)}` : '--' },
  ];

  return <KeyFactsGrid facts={facts} columns={2} />;
}

// ---------------------------------------------------------------------------
// Tab: Relationships
// ---------------------------------------------------------------------------

function RelationshipsTab({ uei }: { uei: string }) {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = usePartnerRelationships(uei, page, 20);

  const columns: GridColDef<PrimeSubRelationshipDto>[] = [
    {
      field: 'primeName',
      headerName: 'Prime',
      flex: 1,
      minWidth: 160,
      renderCell: (params) => {
        const name = params.value as string | null;
        const primeUei = params.row.primeUei;
        if (!name) return '--';
        return (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/teaming/partner/${encodeURIComponent(primeUei)}`);
            }}
          >
            {name}
          </Link>
        );
      },
    },
    {
      field: 'subName',
      headerName: 'Sub',
      flex: 1,
      minWidth: 160,
      renderCell: (params) => {
        const name = params.value as string | null;
        const subUei = params.row.subUei;
        if (!name) return '--';
        return (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/teaming/partner/${encodeURIComponent(subUei)}`);
            }}
          >
            {name}
          </Link>
        );
      },
    },
    {
      field: 'subawardCount',
      headerName: 'Awards',
      width: 90,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatNumber(value),
    },
    {
      field: 'totalSubawardValue',
      headerName: 'Total Value',
      width: 130,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value, true),
    },
    {
      field: 'firstSubawardDate',
      headerName: 'First Award',
      width: 120,
      valueFormatter: (value: string | null | undefined) => formatDate(value),
    },
    {
      field: 'lastSubawardDate',
      headerName: 'Last Award',
      width: 120,
      valueFormatter: (value: string | null | undefined) => formatDate(value),
    },
    {
      field: 'naicsCodesTogether',
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
  ];

  if (isError) {
    return (
      <ErrorState
        title="Failed to load relationships"
        message="Could not retrieve relationship data."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <Box>
      {isLoading && <LoadingState message="Loading relationships..." />}
      {!isLoading && (
        <>
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            loading={false}
            getRowId={(row: PrimeSubRelationshipDto) => `${row.primeUei}-${row.subUei}`}
            sx={{ minHeight: 300 }}
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

// ---------------------------------------------------------------------------
// Tab: Network
// ---------------------------------------------------------------------------

function NetworkTab({ uei }: { uei: string }) {
  const navigate = useNavigate();
  const [depth, setDepth] = useState(1);
  const { data, isLoading, isError, refetch } = usePartnerNetwork(uei, depth);

  const columns: GridColDef<TeamingNetworkNodeDto>[] = [
    {
      field: 'vendorName',
      headerName: 'Vendor',
      flex: 1,
      minWidth: 160,
      renderCell: (params) => {
        const name = params.value as string | null;
        const vendorUei = params.row.vendorUei;
        if (!name) return '--';
        return (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/teaming/partner/${encodeURIComponent(vendorUei)}`);
            }}
          >
            {name}
          </Link>
        );
      },
    },
    {
      field: 'relationshipDirection',
      headerName: 'Direction',
      width: 110,
      renderCell: (params) => {
        const dir = params.value as string;
        const color: ChipColor = dir === 'PRIME_OF' ? 'primary' : dir === 'SUB_TO' ? 'secondary' : 'default';
        return <Chip label={dir} size="small" color={color} variant="outlined" />;
      },
    },
    {
      field: 'partnerName',
      headerName: 'Partner',
      flex: 1,
      minWidth: 160,
      renderCell: (params) => {
        const name = params.value as string | null;
        const partnerUei = params.row.partnerUei;
        if (!name) return '--';
        return (
          <Link
            component="button"
            variant="body2"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/teaming/partner/${encodeURIComponent(partnerUei)}`);
            }}
          >
            {name}
          </Link>
        );
      },
    },
    {
      field: 'awardCount',
      headerName: 'Awards',
      width: 90,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatNumber(value),
    },
    {
      field: 'totalValue',
      headerName: 'Total Value',
      width: 130,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value: number | null | undefined) => formatCurrency(value, true),
    },
  ];

  if (isError) {
    return (
      <ErrorState
        title="Failed to load network"
        message="Could not retrieve network data."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center' }}>
        <Chip
          label="1-Hop"
          color={depth === 1 ? 'primary' : 'default'}
          onClick={() => setDepth(1)}
          variant={depth === 1 ? 'filled' : 'outlined'}
        />
        <Chip
          label="2-Hop"
          color={depth === 2 ? 'primary' : 'default'}
          onClick={() => setDepth(2)}
          variant={depth === 2 ? 'filled' : 'outlined'}
        />
        {data && (
          <Typography variant="body2" color="text.secondary">
            {data.length} connection{data.length !== 1 ? 's' : ''}
          </Typography>
        )}
      </Box>

      {isLoading && <LoadingState message="Loading network..." />}
      {!isLoading && (
        <DataTable
          columns={columns}
          rows={data ?? []}
          loading={false}
          getRowId={(row: TeamingNetworkNodeDto) => `${row.vendorUei}-${row.partnerUei}-${row.relationshipDirection}`}
          sx={{ minHeight: 300 }}
        />
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const TAB_LABELS = ['Capabilities', 'Risk Assessment', 'Relationships', 'Network'];

export default function PartnerDetailPage() {
  const { uei } = useParams<{ uei: string }>();
  const [tab, setTab] = useState(0);

  const { data: risk, isLoading, isError, refetch } = usePartnerRisk(uei ?? '');

  if (isLoading) {
    return (
      <Box>
        <PageHeader title="Partner Detail" subtitle="Loading..." />
        <LoadingState message="Loading partner data..." />
      </Box>
    );
  }

  if (isError || !risk) {
    return (
      <Box>
        <PageHeader title="Partner Detail" subtitle="Error" />
        <ErrorState
          title="Failed to load partner"
          message="Could not retrieve partner data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title={risk.legalBusinessName ?? risk.ueiSam}
        subtitle={`UEI: ${risk.ueiSam}`}
      />

      {/* Header badges */}
      <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
        {riskChip(risk.riskLevel)}
        {risk.currentExclusionFlag && (
          <Chip label="Active Exclusion" size="small" color="error" />
        )}
        {risk.certificationCount > 0 && (
          <Chip
            label={`${risk.certificationCount} Certification${risk.certificationCount !== 1 ? 's' : ''}`}
            size="small"
            color="primary"
            variant="outlined"
          />
        )}
      </Box>

      <Tabs value={tab} onChange={(_e, v: number) => setTab(v)} sx={{ mb: 3 }}>
        {TAB_LABELS.map((label) => (
          <Tab key={label} label={label} />
        ))}
      </Tabs>

      {tab === 0 && <CapabilitiesTab risk={risk} />}
      {tab === 1 && <RiskTab risk={risk} />}
      {tab === 2 && <RelationshipsTab uei={uei ?? ''} />}
      {tab === 3 && <NetworkTab uei={uei ?? ''} />}
    </Box>
  );
}
