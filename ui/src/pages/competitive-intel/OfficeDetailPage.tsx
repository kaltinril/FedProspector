import { useParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Grid from '@mui/material/Grid';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';

import { ErrorState } from '@/components/shared/ErrorState';
import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import { LoadingState } from '@/components/shared/LoadingState';
import { PageHeader } from '@/components/shared/PageHeader';
import { useOfficeProfile } from '@/queries/useCompetitiveIntel';
import { formatCurrency, formatNumber, formatPercent } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface DistributionItem {
  label: string;
  value: number | null | undefined;
  color: string;
}

function DistributionBar({ items, title }: { items: DistributionItem[]; title: string }) {
  const validItems = items.filter((i) => i.value != null && i.value > 0);
  if (validItems.length === 0) {
    return (
      <Box>
        <Typography variant="subtitle2" gutterBottom>{title}</Typography>
        <Typography variant="body2" color="text.secondary">No data available</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>{title}</Typography>
      {validItems.map((item) => (
        <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="body2" sx={{ minWidth: 120, color: 'text.secondary' }}>
            {item.label}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={Math.min(item.value ?? 0, 100)}
            sx={{
              flexGrow: 1,
              height: 10,
              borderRadius: 5,
              '& .MuiLinearProgress-bar': { backgroundColor: item.color },
              backgroundColor: 'action.hover',
            }}
          />
          <Typography variant="body2" sx={{ minWidth: 50, textAlign: 'right' }}>
            {formatPercent(item.value)}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OfficeDetailPage() {
  const { officeCode } = useParams<{ officeCode: string }>();
  const { data, isLoading, isError, refetch } = useOfficeProfile(officeCode ?? '');

  if (isLoading) {
    return (
      <Box>
        <PageHeader title="Office Detail" subtitle="Loading..." />
        <LoadingState message="Loading office profile..." />
      </Box>
    );
  }

  if (isError || !data) {
    return (
      <Box>
        <PageHeader title="Office Detail" subtitle="Error" />
        <ErrorState
          title="Failed to load office profile"
          message="Could not retrieve office data. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  const setAsideItems: DistributionItem[] = [
    { label: 'Small Business', value: data.smallBusinessPct, color: '#1976d2' },
    { label: 'WOSB', value: data.wosbPct, color: '#9c27b0' },
    { label: '8(a)', value: data.eightAPct, color: '#2e7d32' },
    { label: 'HUBZone', value: data.hubzonePct, color: '#ed6c02' },
    { label: 'SDVOSB', value: data.sdvosbPct, color: '#0288d1' },
    { label: 'Unrestricted', value: data.unrestrictedPct, color: '#757575' },
  ];

  const contractTypeItems: DistributionItem[] = [
    { label: 'Firm Fixed Price', value: data.ffpPct, color: '#1976d2' },
    { label: 'Time & Materials', value: data.tmPct, color: '#9c27b0' },
    { label: 'Cost Plus', value: data.costPlusPct, color: '#2e7d32' },
  ];

  const competitionItems: DistributionItem[] = [
    { label: 'Full Competition', value: data.fullCompetitionPct, color: '#2e7d32' },
    { label: 'Sole Source', value: data.soleSourcePct, color: '#d32f2f' },
  ];

  return (
    <Box>
      <PageHeader
        title={data.contractingOfficeName ?? data.contractingOfficeId}
        subtitle={data.agencyName ?? 'Contracting Office'}
      />

      {/* Key facts */}
      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent>
          <KeyFactsGrid
            facts={[
              { label: 'Office Code', value: data.contractingOfficeId },
              { label: 'Agency', value: data.agencyName ?? '--' },
              { label: 'Total Awards', value: formatNumber(data.totalAwards) },
              { label: 'Total Obligated', value: formatCurrency(data.totalObligated, true) },
              { label: 'Avg Award Value', value: formatCurrency(data.avgAwardValue, true) },
              { label: 'Avg Procurement Days', value: data.avgProcurementDays != null ? `${Math.round(data.avgProcurementDays)} days` : '--' },
              { label: 'Earliest Award', value: formatDate(data.earliestAward) },
              { label: 'Latest Award', value: formatDate(data.latestAward) },
              { label: 'Top NAICS', value: data.topNaicsCodes ?? '--', fullWidth: true },
            ]}
            columns={3}
          />
        </CardContent>
      </Card>

      {/* Distribution charts */}
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent>
              <DistributionBar items={setAsideItems} title="Set-Aside Preferences" />
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent>
              <DistributionBar items={contractTypeItems} title="Contract Type Distribution" />
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent>
              <DistributionBar items={competitionItems} title="Competition Preferences" />
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
