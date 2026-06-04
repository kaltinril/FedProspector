import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import LinearProgress from '@mui/material/LinearProgress';
import Grid from '@mui/material/Grid';
import Chip from '@mui/material/Chip';
import Alert from '@mui/material/Alert';
import Divider from '@mui/material/Divider';
import Tooltip from '@mui/material/Tooltip';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { useSizeStandardAlerts } from '@/queries/useOnboarding';
import { useAffiliatedSizeEligibility } from '@/queries/useOrganization';
import { formatCurrency } from '@/utils/formatters';

function thresholdColor(pct: number | null | undefined): 'error' | 'warning' | 'success' {
  if (pct == null) return 'success';
  if (pct >= 80) return 'error';
  if (pct >= 60) return 'warning';
  return 'success';
}

function progressColor(pct: number | null | undefined): 'error' | 'warning' | 'success' {
  if (pct == null) return 'success';
  if (pct >= 80) return 'error';
  if (pct >= 60) return 'warning';
  return 'success';
}

function formatValue(value: number | null | undefined, type: string | null | undefined): string {
  if (value == null) return '--';
  if (type === 'R') {
    return formatCurrency(value * 1000000, true);
  }
  if (type === 'E') {
    return value.toLocaleString();
  }
  return value.toLocaleString();
}

/** Renders a verdict label ("Small" / "Other than small" / "—") for an eligibility boolean. */
function verdictLabel(eligible: boolean | null | undefined): string {
  if (eligible == null) return '—';
  return eligible ? 'Small' : 'Other than small';
}

/**
 * Phase 133 Task 6: affiliation-aware size determination for a single NAICS card.
 * Shows BOTH the standalone (org-only) and affiliated (org + included affiliates) verdicts
 * and a prominent callout when the org is small alone but other-than-small once affiliates roll in.
 */
function AffiliatedSizeRow({ naicsCode }: { naicsCode: string }) {
  const { data, isLoading, isError } = useAffiliatedSizeEligibility(naicsCode);

  if (isLoading || isError || !data) return null;

  // Nothing useful to add when there are no affiliates and no determination differs.
  const hasAffiliates =
    data.affiliateCount > 0 ||
    data.includedAffiliates.length > 0 ||
    data.excludedAffiliates.length > 0;
  const verdictsDiffer =
    data.standaloneEligible != null &&
    data.affiliatedEligible != null &&
    data.standaloneEligible !== data.affiliatedEligible;

  if (!hasAffiliates && !verdictsDiffer) return null;

  return (
    <>
      <Divider sx={{ my: 1.5 }} />
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
        Affiliation roll-up (13 CFR 121.103)
      </Typography>

      {data.flippedToOtherThanSmall && (
        <Alert severity="warning" sx={{ mb: 1, py: 0.5 }}>
          Small standalone, but <strong>other-than-small</strong> once affiliates are combined.
          The combined enterprise determines your size for set-asides.
        </Alert>
      )}

      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 0.5 }}>
        <Chip
          size="small"
          variant="outlined"
          color={data.standaloneEligible === false ? 'error' : 'default'}
          label={`Standalone: ${verdictLabel(data.standaloneEligible)}`}
        />
        <Chip
          size="small"
          variant="outlined"
          color={data.affiliatedEligible === false ? 'error' : 'success'}
          label={`With affiliates: ${verdictLabel(data.affiliatedEligible)}`}
        />
      </Box>

      <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
        {data.reason}
      </Typography>

      {data.includedAffiliates.length > 0 && (
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
          Counted: {data.includedAffiliates.map((a) => `${a.uei} (${a.relationship})`).join(', ')}
        </Typography>
      )}

      {data.excludedAffiliates.length > 0 && (
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block' }}>
          Excluded:{' '}
          {data.excludedAffiliates
            .map((a) => `${a.uei} (${a.reason === 'APPROVED_MPA' ? 'approved MPA' : 'teaming'})`)
            .join(', ')}
        </Typography>
      )}

      {data.missingAffiliateData.length > 0 && (
        <Tooltip title="These affiliates have no revenue/headcount entered, so the combined total is a lower bound. Enter their figures on the Linked Entities tab.">
          <Typography variant="caption" sx={{ color: 'warning.main', display: 'block', mt: 0.5 }}>
            Missing data for {data.missingAffiliateData.length} affiliate(s) — total is a lower bound.
          </Typography>
        </Tooltip>
      )}
    </>
  );
}

export default function SizeStandardMonitorPage() {
  const { data: alerts, isLoading, isError, refetch } = useSizeStandardAlerts();

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  if (!alerts || alerts.length === 0) {
    return (
      <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
        <PageHeader
          title="Size Standard Monitor"
          subtitle="Track SBA size standard thresholds by NAICS code"
        />
        <EmptyState
          title="No Size Standards"
          message="No size standard data available. Add NAICS codes and size standard information to your organization profile."
        />
      </Box>
    );
  }

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader
        title="Size Standard Monitor"
        subtitle={`Monitoring ${alerts.length} NAICS code${alerts.length !== 1 ? 's' : ''} against SBA thresholds`}
      />
      <Grid container spacing={2}>
        {alerts.map((alert) => {
          const pct = alert.pctOfThreshold ?? 0;
          const clampedPct = Math.min(pct, 100);
          const color = thresholdColor(pct);

          return (
            <Grid key={alert.naicsCode} size={{ xs: 12, sm: 6, md: 4 }}>
              <Card
                sx={{
                  borderLeft: 4,
                  borderColor: `${color}.main`,
                }}
              >
                <CardContent>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="h6" component="div">
                      {alert.naicsCode}
                    </Typography>
                    {pct >= 80 && (
                      <Chip
                        label="Approaching Limit"
                        size="small"
                        color="error"
                        variant="outlined"
                      />
                    )}
                  </Box>

                  {alert.sizeStandardType && (
                    <Typography
                      variant="body2"
                      sx={{
                        color: "text.secondary",
                        mb: 1
                      }}>
                      Type: {alert.sizeStandardType}
                    </Typography>
                  )}

                  <Box sx={{ mb: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="body2">
                        Current: {formatValue(alert.currentValue, alert.sizeStandardType)}
                      </Typography>
                      <Typography variant="body2">
                        Threshold: {formatValue(alert.threshold, alert.sizeStandardType)}
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={clampedPct}
                      color={progressColor(pct)}
                      sx={{ height: 10, borderRadius: 5 }}
                    />
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        mt: 0.5,
                        display: 'block'
                      }}>
                      {pct.toFixed(1)}% of threshold
                    </Typography>
                  </Box>

                  <AffiliatedSizeRow naicsCode={alert.naicsCode} />
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}
