import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import Chip from '@mui/material/Chip';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import ListItemSecondaryAction from '@mui/material/ListItemSecondaryAction';
import Button from '@mui/material/Button';
import Skeleton from '@mui/material/Skeleton';
import Alert from '@mui/material/Alert';
import AssignmentIcon from '@mui/icons-material/Assignment';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import AttachMoneyIcon from '@mui/icons-material/AttachMoney';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import type { GridColDef, GridRowParams } from '@mui/x-data-grid';
import { BarChart } from '@mui/x-charts/BarChart';

import { useDashboard } from '@/queries/useDashboard';
import { PageHeader } from '@/components/shared/PageHeader';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { DataTable } from '@/components/shared/DataTable';
import { formatCurrency } from '@/utils/formatters';
import { formatCountdown, formatRelative } from '@/utils/dateFormatters';
import { getRecommendedOpportunities } from '@/api/opportunities';
import { getExpiringContracts } from '@/api/awards';
import { queryKeys } from '@/queries/queryKeys';
import type { DueOpportunityDto, RecommendedOpportunityDto, ExpiringContractDto } from '@/types/api';

// ---------------------------------------------------------------------------
// StatCard
// ---------------------------------------------------------------------------

function StatCard({
  title,
  value,
  icon,
  color,
  onClick,
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color?: string;
  onClick?: () => void;
}) {
  return (
    <Card
      sx={{
        cursor: onClick ? 'pointer' : 'default',
        '&:hover': onClick ? { boxShadow: 6 } : undefined,
      }}
      onClick={onClick}
    >
      <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box
          sx={{
            bgcolor: color ?? 'primary.main',
            color: 'common.white',
            borderRadius: 2,
            p: 1.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {icon}
        </Box>
        <Box>
          <Typography variant="h5" fontWeight="bold">
            {value}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {title}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Due This Week columns
// ---------------------------------------------------------------------------

const dueColumns: GridColDef[] = [
  {
    field: 'title',
    headerName: 'Title',
    flex: 2,
    minWidth: 200,
  },
  {
    field: 'responseDeadline',
    headerName: 'Deadline',
    width: 130,
    valueGetter: (_value, row) => row.responseDeadline,
    renderCell: (params) => {
      const text = formatCountdown(params.value as string | null);
      const isExpired = text === 'Expired';
      return (
        <Typography
          variant="body2"
          color={isExpired ? 'error.main' : 'text.primary'}
          fontWeight={isExpired ? 'bold' : undefined}
        >
          {text}
        </Typography>
      );
    },
  },
  { field: 'assignedTo', headerName: 'Assigned To', width: 130 },
  { field: 'status', headerName: 'Status', width: 110 },
  { field: 'priority', headerName: 'Priority', width: 100 },
  { field: 'setAsideCode', headerName: 'Set-Aside', width: 100 },
];

// ---------------------------------------------------------------------------
// DashboardPage
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError, refetch } = useDashboard();

  const { data: recommendations, isLoading: recsLoading } = useQuery({
    queryKey: queryKeys.opportunities.recommended(5),
    queryFn: () => getRecommendedOpportunities(5),
    staleTime: 5 * 60 * 1000,
  });

  const { data: expiringSoon, isLoading: expiringLoading } = useQuery({
    queryKey: queryKeys.awards.expiring({ monthsAhead: 6, limit: 5 }),
    queryFn: () => getExpiringContracts({ monthsAhead: 6, limit: 5 }),
    staleTime: 5 * 60 * 1000,
  });

  // Compute win rate
  const winRate = useMemo(() => {
    if (!data) return 'N/A';
    const won =
      data.winLossMetrics.find((m) => m.outcome === 'WON')?.count ?? 0;
    const lost =
      data.winLossMetrics.find((m) => m.outcome === 'LOST')?.count ?? 0;
    const total = won + lost;
    if (total === 0) return 'N/A';
    return `${((won / total) * 100).toFixed(1)}%`;
  }, [data]);

  // Detect overdue items
  const hasOverdue = useMemo(() => {
    if (!data) return false;
    return data.dueThisWeek.some((d) => {
      if (!d.responseDeadline) return false;
      return new Date(d.responseDeadline) < new Date();
    });
  }, [data]);

  // ---- Loading / Error ----
  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => refetch()} />;

  // ---- Empty state ----
  if (data.totalOpenProspects === 0) {
    return (
      <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
        <PageHeader title="Dashboard" />
        <Box
          sx={{
            textAlign: 'center',
            py: 8,
          }}
        >
          <Typography variant="h5" gutterBottom>
            No active prospects
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            Get started by searching for opportunities and adding them to your
            pipeline.
          </Typography>
          <Button
            variant="contained"
            onClick={() => navigate('/opportunities')}
          >
            Search Opportunities
          </Button>
        </Box>
      </Box>
    );
  }

  // ---- Pipeline chart data ----
  const pipelineDataset = data.prospectsByStatus.map((s) => ({
    status: s.status,
    count: s.count,
  }));

  // ---- Workload chart data ----
  const workloadDataset = data.workloadByAssignee.map((a) => ({
    name: a.displayName ?? a.username,
    count: a.count,
  }));

  // ---- Win/Loss chart data ----
  const winLossDataset = data.winLossMetrics.map((m) => ({
    outcome: m.outcome,
    count: m.count,
  }));

  return (
    <Box sx={{ p: { xs: 2, sm: 3, md: 4 } }}>
      <PageHeader title="Dashboard" subtitle="Pipeline overview and key metrics" />

      {/* Row 1: Key Metrics */}
      <Grid container spacing={{ xs: 1.5, sm: 2, md: 3 }} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Total Open Prospects"
            value={data.totalOpenProspects}
            icon={<AssignmentIcon />}
            color="#1976d2"
            onClick={() => navigate('/prospects')}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Due This Week"
            value={data.dueThisWeek.length}
            icon={<WarningAmberIcon />}
            color={hasOverdue ? '#d32f2f' : '#ed6c02'}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Win Rate"
            value={winRate}
            icon={<TrendingUpIcon />}
            color="#2e7d32"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Pipeline Value"
            value={formatCurrency(data.pipelineValue, true)}
            icon={<AttachMoneyIcon />}
            color="#9c27b0"
          />
        </Grid>
        {data.autoMatchCount > 0 && (
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <StatCard
              title="Auto-Matches (7d)"
              value={data.autoMatchCount}
              icon={<AutoAwesomeIcon />}
              color="#00897b"
              onClick={() => navigate('/prospects?source=AUTO_MATCH')}
            />
          </Grid>
        )}
      </Grid>

      {/* Row 2: Intelligence Widgets */}
      <Grid container spacing={{ xs: 1.5, sm: 2, md: 3 }} sx={{ mb: 3 }}>
        {/* Top Recommendations */}
        <Grid size={{ xs: 12, md: 7 }}>
          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">Top Recommendations</Typography>
              <Button size="small" onClick={() => navigate('/opportunities/recommended')}>
                View All
              </Button>
            </Box>
            {recsLoading ? (
              <Box>
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} height={56} sx={{ mb: 0.5 }} />
                ))}
              </Box>
            ) : !recommendations || recommendations.length === 0 ? (
              <Alert severity="info">
                No recommendations yet. Link your SAM.gov entity to get started.
              </Alert>
            ) : (
              <List disablePadding>
                {recommendations.map((rec: RecommendedOpportunityDto) => (
                  <ListItemButton
                    key={rec.noticeId}
                    divider
                    onClick={() => navigate(`/opportunities/${encodeURIComponent(rec.noticeId)}`)}
                    sx={{ px: 1 }}
                  >
                    <ListItemText
                      primary={rec.title ?? rec.solicitationNumber ?? rec.noticeId}
                      secondary={rec.departmentName ?? undefined}
                      primaryTypographyProps={{ variant: 'body2', fontWeight: 500, noWrap: true }}
                      secondaryTypographyProps={{ variant: 'caption', noWrap: true }}
                    />
                    <Box sx={{ display: 'flex', gap: 1, ml: 1, flexShrink: 0 }}>
                      {rec.daysRemaining != null && (
                        <Chip
                          label={`${rec.daysRemaining}d`}
                          size="small"
                          color={rec.daysRemaining < 7 ? 'error' : rec.daysRemaining < 14 ? 'warning' : 'default'}
                          variant="outlined"
                        />
                      )}
                      <Chip
                        label={rec.qScore}
                        size="small"
                        color={rec.qScore >= 70 ? 'success' : rec.qScore >= 40 ? 'warning' : 'error'}
                      />
                    </Box>
                  </ListItemButton>
                ))}
              </List>
            )}
          </Paper>
        </Grid>

        {/* Expiring Soon */}
        <Grid size={{ xs: 12, md: 5 }}>
          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">Expiring Soon</Typography>
              <Button size="small" onClick={() => navigate('/awards/expiring')}>
                View All
              </Button>
            </Box>
            {expiringLoading ? (
              <Box>
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} height={56} sx={{ mb: 0.5 }} />
                ))}
              </Box>
            ) : !expiringSoon || expiringSoon.length === 0 ? (
              <Alert severity="info">
                No expiring contracts found matching your NAICS codes.
              </Alert>
            ) : (
              <List disablePadding>
                {expiringSoon.map((contract: ExpiringContractDto) => (
                  <ListItemButton
                    key={contract.piid}
                    divider
                    onClick={() => navigate(`/awards/${encodeURIComponent(contract.piid)}`)}
                    sx={{ px: 1 }}
                  >
                    <ListItemText
                      primary={contract.description ?? contract.piid}
                      secondary={contract.vendorName ?? undefined}
                      primaryTypographyProps={{ variant: 'body2', fontWeight: 500, noWrap: true }}
                      secondaryTypographyProps={{ variant: 'caption', noWrap: true }}
                    />
                    <Box sx={{ display: 'flex', gap: 1, ml: 1, flexShrink: 0 }}>
                      {contract.contractValue != null && (
                        <Chip
                          label={formatCurrency(contract.contractValue, true)}
                          size="small"
                          variant="outlined"
                        />
                      )}
                      <Chip
                        label={contract.monthsRemaining != null ? `${contract.monthsRemaining}mo` : '--'}
                        size="small"
                        color={
                          contract.monthsRemaining == null ? 'default' :
                          contract.monthsRemaining < 3 ? 'error' :
                          contract.monthsRemaining < 6 ? 'warning' : 'success'
                        }
                      />
                    </Box>
                  </ListItemButton>
                ))}
              </List>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Row 3: Pipeline Overview */}
      <Paper sx={{ p: { xs: 2, md: 3 }, mb: 3 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          Pipeline Overview
        </Typography>
        {pipelineDataset.length > 0 ? (
          <Box sx={{ width: '100%', height: Math.max(250, pipelineDataset.length * 45), overflowX: 'auto' }}>
            <BarChart
              dataset={pipelineDataset}
              yAxis={[{ scaleType: 'band', dataKey: 'status' }]}
              series={[
                {
                  dataKey: 'count',
                  label: 'Prospects',
                  valueFormatter: (v) => String(v ?? 0),
                },
              ]}
              layout="horizontal"
              margin={{ left: 140 }}
              onAxisClick={(_event, data) => {
                if (data?.axisValue) {
                  navigate(`/prospects?status=${encodeURIComponent(String(data.axisValue))}`);
                }
              }}
            />
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No pipeline data available.
          </Typography>
        )}
      </Paper>

      {/* Row 3: Due This Week + Workload */}
      <Grid container spacing={{ xs: 1.5, sm: 2, md: 3 }} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, md: 7 }}>
          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Due This Week
            </Typography>
            <DataTable
              columns={dueColumns}
              rows={data.dueThisWeek}
              getRowId={(row: DueOpportunityDto) => row.prospectId}
              onRowClick={(params: GridRowParams) =>
                navigate(`/prospects/${params.id}`)
              }
              sx={{ maxHeight: 400 }}
            />
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 5 }}>
          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Workload by Assignee
            </Typography>
            {workloadDataset.length > 0 ? (
              <Box sx={{ width: '100%', height: Math.max(250, workloadDataset.length * 45), overflowX: 'auto' }}>
                <BarChart
                  dataset={workloadDataset}
                  yAxis={[{ scaleType: 'band', dataKey: 'name' }]}
                  series={[
                    {
                      dataKey: 'count',
                      label: 'Assigned',
                      valueFormatter: (v) => String(v ?? 0),
                    },
                  ]}
                  layout="horizontal"
                  margin={{ left: 140 }}
                />
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No assignee data available.
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>

      {/* Row 4: Win/Loss + Recent Saved Searches */}
      <Grid container spacing={{ xs: 1.5, sm: 2, md: 3 }}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Win / Loss Metrics
            </Typography>
            {winLossDataset.length > 0 ? (
              <Box sx={{ width: '100%', height: 250 }}>
                <BarChart
                  dataset={winLossDataset}
                  xAxis={[{ scaleType: 'band', dataKey: 'outcome' }]}
                  series={[
                    {
                      dataKey: 'count',
                      label: 'Count',
                      valueFormatter: (v) => String(v ?? 0),
                    },
                  ]}
                />
              </Box>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No outcome data yet.
              </Typography>
            )}
          </Paper>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <Paper sx={{ p: { xs: 2, md: 3 } }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Recent Saved Searches
            </Typography>
            {data.recentSavedSearches.length > 0 ? (
              <List disablePadding>
                {data.recentSavedSearches.slice(0, 5).map((ss) => (
                  <ListItem
                    key={ss.searchId}
                    divider
                    sx={{
                      cursor: 'pointer',
                      '&:hover': { bgcolor: 'action.hover' },
                    }}
                    onClick={() => navigate('/saved-searches')}
                  >
                    <ListItemText
                      primary={ss.searchName}
                      secondary={
                        ss.lastRunAt
                          ? `Last run ${formatRelative(ss.lastRunAt)}`
                          : 'Never run'
                      }
                    />
                    <ListItemSecondaryAction>
                      {ss.lastNewResults != null && ss.lastNewResults > 0 && (
                        <Chip
                          label={`${ss.lastNewResults} new`}
                          color="primary"
                          size="small"
                        />
                      )}
                    </ListItemSecondaryAction>
                  </ListItem>
                ))}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No saved searches yet. Save a search from the opportunities
                page to see it here.
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
