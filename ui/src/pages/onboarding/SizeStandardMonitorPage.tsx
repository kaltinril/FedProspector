import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import LinearProgress from '@mui/material/LinearProgress';
import Grid from '@mui/material/Grid';
import Chip from '@mui/material/Chip';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { useSizeStandardAlerts } from '@/queries/useOnboarding';
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
  if (type?.toLowerCase().includes('revenue') || type?.toLowerCase().includes('dollar')) {
    return formatCurrency(value, true);
  }
  return value.toLocaleString();
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
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
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
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                      {pct.toFixed(1)}% of threshold
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}
