import { useMemo } from 'react';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Tooltip from '@mui/material/Tooltip';

import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { usePipelineFunnel } from '@/queries/usePipeline';
import { formatCurrency } from '@/utils/formatters';
import type { PipelineFunnelDto } from '@/types/pipeline';

// ---------------------------------------------------------------------------
// Funnel Stage Order
// ---------------------------------------------------------------------------

const STAGE_ORDER = ['NEW', 'REVIEWING', 'PURSUING', 'BID_SUBMITTED', 'WON', 'LOST', 'DECLINED'];

const STAGE_COLORS: Record<string, string> = {
  NEW: '#42a5f5',
  REVIEWING: '#66bb6a',
  PURSUING: '#ffa726',
  BID_SUBMITTED: '#ab47bc',
  WON: '#26a69a',
  LOST: '#ef5350',
  DECLINED: '#bdbdbd',
};

// ---------------------------------------------------------------------------
// FunnelBar
// ---------------------------------------------------------------------------

function FunnelBar({
  stage,
  maxCount,
}: {
  stage: PipelineFunnelDto;
  maxCount: number;
}) {
  const widthPct = maxCount > 0 ? Math.max((stage.prospectCount / maxCount) * 100, 4) : 4;
  const color = STAGE_COLORS[stage.status] ?? '#90a4ae';

  return (
    <Box sx={{ mb: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="body2" fontWeight={600}>
          {stage.status.replace(/_/g, ' ')}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {stage.prospectCount} prospect{stage.prospectCount !== 1 ? 's' : ''}
        </Typography>
      </Box>
      <Tooltip
        title={`Value: ${formatCurrency(stage.totalEstimatedValue, true)}`}
        arrow
      >
        <Box
          sx={{
            width: `${widthPct}%`,
            bgcolor: color,
            borderRadius: 1,
            py: 1,
            px: 2,
            minWidth: 60,
            transition: 'width 0.3s ease',
          }}
        >
          <Typography variant="caption" sx={{ color: 'common.white', fontWeight: 600 }}>
            {formatCurrency(stage.totalEstimatedValue, true)}
          </Typography>
        </Box>
      </Tooltip>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// ConversionRates
// ---------------------------------------------------------------------------

function ConversionRates({ stages }: { stages: PipelineFunnelDto[] }) {
  const activeStages = stages.filter(
    (s) => !['WON', 'LOST', 'DECLINED'].includes(s.status),
  );

  const conversions: { from: string; to: string; rate: string }[] = [];
  for (let i = 0; i < activeStages.length - 1; i++) {
    const from = activeStages[i];
    const to = activeStages[i + 1];
    if (from.prospectCount > 0) {
      const rate = ((to.prospectCount / from.prospectCount) * 100).toFixed(1);
      conversions.push({
        from: from.status.replace(/_/g, ' '),
        to: to.status.replace(/_/g, ' '),
        rate: `${rate}%`,
      });
    }
  }

  if (conversions.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        Not enough data to calculate conversion rates.
      </Typography>
    );
  }

  return (
    <Box>
      {conversions.map((c) => (
        <Box
          key={`${c.from}-${c.to}`}
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            py: 1,
            borderBottom: 1,
            borderColor: 'divider',
          }}
        >
          <Typography variant="body2">
            {c.from} &rarr; {c.to}
          </Typography>
          <Typography variant="body2" fontWeight={600}>
            {c.rate}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// PipelineAnalyticsPage
// ---------------------------------------------------------------------------

export default function PipelineAnalyticsPage() {
  const { data: stages, isLoading, isError, refetch } = usePipelineFunnel();

  const sortedStages = useMemo(() => {
    if (!stages) return [];
    return [...stages].sort(
      (a, b) => STAGE_ORDER.indexOf(a.status) - STAGE_ORDER.indexOf(b.status),
    );
  }, [stages]);

  const maxCount = useMemo(
    () => Math.max(...(sortedStages.map((s) => s.prospectCount) || [1]), 1),
    [sortedStages],
  );

  const winRate = useMemo(() => {
    if (!stages) return null;
    const wonStage = stages.find((s) => s.status === 'WON');
    const lostStage = stages.find((s) => s.status === 'LOST');
    const won = wonStage?.wonCount ?? wonStage?.prospectCount ?? 0;
    const lost = lostStage?.lostCount ?? lostStage?.prospectCount ?? 0;
    const total = won + lost;
    if (total === 0) return null;
    return (won / total) * 100;
  }, [stages]);

  const totalValue = useMemo(() => {
    if (!stages) return 0;
    return stages.reduce((sum, s) => sum + (s.totalEstimatedValue ?? 0), 0);
  }, [stages]);

  const totalProspects = useMemo(() => {
    if (!stages) return 0;
    return stages.reduce((sum, s) => sum + s.prospectCount, 0);
  }, [stages]);

  if (isLoading) return <LoadingState />;
  if (isError || !stages) return <ErrorState onRetry={() => refetch()} />;

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader
        title="Pipeline Analytics"
        subtitle="Funnel visualization, conversion rates, and win metrics"
      />

      {/* Summary cards */}
      <Grid container spacing={{ xs: 1.5, sm: 2, md: 3 }} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="h3" fontWeight={700} color="primary.main">
              {totalProspects}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Prospects
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="h3" fontWeight={700} color="success.main">
              {winRate != null ? `${winRate.toFixed(1)}%` : 'N/A'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Win Rate
            </Typography>
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Paper sx={{ p: 3, textAlign: 'center' }}>
            <Typography variant="h3" fontWeight={700} color="secondary.main">
              {formatCurrency(totalValue, true)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Pipeline Value
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Funnel + Conversion */}
      <Grid container spacing={{ xs: 1.5, sm: 2, md: 3 }}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Pipeline Funnel
            </Typography>
            {sortedStages.length > 0 ? (
              sortedStages.map((stage) => (
                <FunnelBar key={stage.status} stage={stage} maxCount={maxCount} />
              ))
            ) : (
              <Typography variant="body2" color="text.secondary">
                No pipeline data available.
              </Typography>
            )}
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Stage Conversion Rates
            </Typography>
            <ConversionRates stages={sortedStages} />
          </Paper>

          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Avg Time in Stage
            </Typography>
            {sortedStages
              .filter((s) => s.avgHoursInPriorStatus != null)
              .map((s) => (
                <Box
                  key={s.status}
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    py: 1,
                    borderBottom: 1,
                    borderColor: 'divider',
                  }}
                >
                  <Typography variant="body2">
                    {s.status.replace(/_/g, ' ')}
                  </Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {s.avgHoursInPriorStatus != null
                      ? `${(s.avgHoursInPriorStatus / 24).toFixed(1)}d`
                      : '--'}
                  </Typography>
                </Box>
              ))}
            {sortedStages.filter((s) => s.avgHoursInPriorStatus != null).length === 0 && (
              <Typography variant="body2" color="text.secondary">
                No timing data available yet.
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
