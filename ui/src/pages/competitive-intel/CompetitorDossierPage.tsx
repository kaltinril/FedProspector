import { useState } from 'react';
import { useParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import Link from '@mui/material/Link';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';

import { ErrorState } from '@/components/shared/ErrorState';
import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import { LoadingState } from '@/components/shared/LoadingState';
import { PageHeader } from '@/components/shared/PageHeader';
import { useCompetitorDossier } from '@/queries/useCompetitiveIntel';
import { formatCurrency, formatNumber } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import type { CompetitorDossierDto } from '@/types/competitiveIntel';

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

function registrationChip(status: string | null | undefined) {
  if (!status) return '--';
  const color: ChipColor = status === 'Active' ? 'success' : 'warning';
  return <Chip label={status} size="small" color={color} variant="outlined" />;
}

// ---------------------------------------------------------------------------
// Tab panels
// ---------------------------------------------------------------------------

function OverviewTab({ d }: { d: CompetitorDossierDto }) {
  const facts = [
    { label: 'UEI', value: d.ueiSam },
    { label: 'DBA Name', value: d.dbaName ?? '--' },
    { label: 'Registration Status', value: registrationChip(d.registrationStatus) },
    { label: 'Registration Expires', value: formatDate(d.registrationExpirationDate) },
    { label: 'Primary NAICS', value: d.primaryNaics ?? '--' },
    { label: 'Website', value: d.entityUrl ? <Link href={d.entityUrl} target="_blank" rel="noopener">{d.entityUrl}</Link> : '--' },
    { label: 'FPDS Total Contracts', value: formatNumber(d.fpdsContractCount) },
    { label: 'FPDS Total Obligated', value: formatCurrency(d.fpdsTotalObligated, true) },
    { label: 'USA Spending Contracts', value: formatNumber(d.usaContractCount) },
    { label: 'USA Spending Obligated', value: formatCurrency(d.usaTotalObligated, true) },
  ];

  return <KeyFactsGrid facts={facts} columns={2} />;
}

function ContractHistoryTab({ d }: { d: CompetitorDossierDto }) {
  return (
    <Grid container spacing={3}>
      {/* FPDS */}
      <Grid size={{ xs: 12, md: 6 }}>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle1" gutterBottom>FPDS Contract History</Typography>
            <KeyFactsGrid
              facts={[
                { label: '3-Year Count', value: formatNumber(d.fpdsCount3yr) },
                { label: '3-Year Obligated', value: formatCurrency(d.fpdsObligated3yr, true) },
                { label: '5-Year Count', value: formatNumber(d.fpdsCount5yr) },
                { label: '5-Year Obligated', value: formatCurrency(d.fpdsObligated5yr, true) },
                { label: 'Avg Contract Value', value: formatCurrency(d.fpdsAvgContractValue, true) },
                { label: 'Most Recent Award', value: formatDate(d.fpdsMostRecentAward) },
                { label: 'Top Agencies', value: d.fpdsTopAgencies ?? '--', fullWidth: true },
                { label: 'Top NAICS', value: d.fpdsTopNaics ?? '--', fullWidth: true },
              ]}
              columns={2}
            />
          </CardContent>
        </Card>
      </Grid>

      {/* USASpending */}
      <Grid size={{ xs: 12, md: 6 }}>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle1" gutterBottom>USASpending History</Typography>
            <KeyFactsGrid
              facts={[
                { label: 'Total Contracts', value: formatNumber(d.usaContractCount) },
                { label: 'Total Obligated', value: formatCurrency(d.usaTotalObligated, true) },
                { label: '3-Year Obligated', value: formatCurrency(d.usaObligated3yr, true) },
                { label: '5-Year Obligated', value: formatCurrency(d.usaObligated5yr, true) },
                { label: 'Most Recent Award', value: formatDate(d.usaMostRecentAward) },
                { label: 'Top Agencies', value: d.usaTopAgencies ?? '--', fullWidth: true },
              ]}
              columns={2}
            />
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}

function CapabilitiesTab({ d }: { d: CompetitorDossierDto }) {
  const naicsList = splitTags(d.registeredNaicsCodes);
  const certList = splitTags(d.sbaCertifications);
  const bizTypes = splitTags(d.businessTypeCodes);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Typography variant="subtitle1" gutterBottom>NAICS Codes</Typography>
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {naicsList.length > 0 ? naicsList.map((n) => (
            <Chip key={n} label={n} size="small" variant="outlined" />
          )) : (
            <Typography variant="body2" color="text.secondary">None registered</Typography>
          )}
        </Box>
      </Box>

      <Divider />

      <Box>
        <Typography variant="subtitle1" gutterBottom>SBA Certifications</Typography>
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {certList.length > 0 ? certList.map((c) => (
            <Chip key={c} label={c} size="small" color="primary" variant="outlined" />
          )) : (
            <Typography variant="body2" color="text.secondary">None listed</Typography>
          )}
        </Box>
      </Box>

      <Divider />

      <Box>
        <Typography variant="subtitle1" gutterBottom>Business Types</Typography>
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {bizTypes.length > 0 ? bizTypes.map((b) => (
            <Chip key={b} label={b} size="small" variant="outlined" />
          )) : (
            <Typography variant="body2" color="text.secondary">None listed</Typography>
          )}
        </Box>
      </Box>
    </Box>
  );
}

function SubcontractingTab({ d }: { d: CompetitorDossierDto }) {
  return (
    <Grid container spacing={3}>
      <Grid size={{ xs: 12, md: 6 }}>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle1" gutterBottom>As Subcontractor</Typography>
            <KeyFactsGrid
              facts={[
                { label: 'Sub Awards', value: formatNumber(d.subContractCount) },
                { label: 'Total Value', value: formatCurrency(d.subTotalValue, true) },
                { label: 'Avg Sub Value', value: formatCurrency(d.subAvgValue, true) },
              ]}
              columns={2}
            />
          </CardContent>
        </Card>
      </Grid>
      <Grid size={{ xs: 12, md: 6 }}>
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle1" gutterBottom>As Prime (Sub Awards Given)</Typography>
            <KeyFactsGrid
              facts={[
                { label: 'Sub Awards Given', value: formatNumber(d.primeSubAwardsCount) },
                { label: 'Total Given Value', value: formatCurrency(d.primeSubTotalValue, true) },
              ]}
              columns={2}
            />
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const TAB_LABELS = ['Overview', 'Contract History', 'Capabilities', 'Subcontracting'];

export default function CompetitorDossierPage() {
  const { uei } = useParams<{ uei: string }>();
  const [tab, setTab] = useState(0);

  const { data, isLoading, isError, refetch } = useCompetitorDossier(uei ?? '');

  if (isLoading) {
    return (
      <Box>
        <PageHeader title="Competitor Dossier" subtitle="Loading..." />
        <LoadingState message="Loading competitor data..." />
      </Box>
    );
  }

  if (isError || !data) {
    return (
      <Box>
        <PageHeader title="Competitor Dossier" subtitle="Error" />
        <ErrorState
          title="Failed to load competitor"
          message="Could not retrieve competitor data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title={data.legalBusinessName ?? data.ueiSam}
        subtitle={`UEI: ${data.ueiSam}`}
      />

      {/* Status chips */}
      <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
        {registrationChip(data.registrationStatus)}
        {data.primaryNaics && (
          <Chip label={`NAICS: ${data.primaryNaics}`} size="small" variant="outlined" />
        )}
      </Box>

      <Tabs value={tab} onChange={(_e, v: number) => setTab(v)} sx={{ mb: 3 }}>
        {TAB_LABELS.map((label) => (
          <Tab key={label} label={label} />
        ))}
      </Tabs>

      {tab === 0 && <OverviewTab d={data} />}
      {tab === 1 && <ContractHistoryTab d={data} />}
      {tab === 2 && <CapabilitiesTab d={data} />}
      {tab === 3 && <SubcontractingTab d={data} />}
    </Box>
  );
}
