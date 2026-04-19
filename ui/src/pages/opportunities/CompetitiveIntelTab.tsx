import { useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import VulnerabilitySignals from '@/components/shared/VulnerabilitySignals';
import MarketShareChart from '@/components/shared/MarketShareChart';
import SetAsideTrendChart from '@/components/shared/SetAsideTrendChart';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import PartnerCompatibilitySection from './PartnerCompatibilitySection';
import OpenDoorSection from './OpenDoorSection';
import { getIncumbentAnalysis, getCompetitiveLandscape, getSetAsideShift, getIvs, getOpportunityCompetitors } from '@/api/opportunities';
import { getIntelMarketShare, getSetAsideTrends } from '@/api/awards';
import { queryKeys } from '@/queries/queryKeys';
import { formatCurrency, formatPercent, formatNumber } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import Skeleton from '@mui/material/Skeleton';
import type { OpportunityDetail, CompetitiveLandscapeDto, LikelyCompetitorDto, SetAsideShiftDto } from '@/types/api';

// ---------------------------------------------------------------------------
// Set-Aside Shift Card
// ---------------------------------------------------------------------------

function SetAsideShiftCard({ shift }: { shift: SetAsideShiftDto }) {
  // null means no predecessor found
  if (shift.shiftDetected == null) {
    return null;
  }

  const isShifted = shift.shiftDetected === true;

  return (
    <Alert
      severity={isShifted ? 'warning' : 'info'}
      variant="outlined"
      sx={{ mb: 3 }}
    >
      <AlertTitle>
        {isShifted ? 'Set-Aside Shift Detected' : 'Same Set-Aside as Predecessor'}
      </AlertTitle>
      {isShifted ? (
        <Typography variant="body2">
          Changed from <strong>{shift.predecessorSetAsideType ?? 'Unknown'}</strong> to{' '}
          <strong>{shift.currentSetAsideDescription ?? shift.currentSetAsideCode ?? 'Unknown'}</strong>
        </Typography>
      ) : (
        <Typography variant="body2">
          Continuing as{' '}
          <strong>
            {shift.currentSetAsideDescription ?? shift.currentSetAsideCode ?? 'Unknown'}
          </strong>
        </Typography>
      )}
      {shift.predecessorVendorName && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="body2" sx={{
            color: "text.secondary"
          }}>
            Predecessor: {shift.predecessorVendorName}
            {shift.predecessorVendorUei ? ` (${shift.predecessorVendorUei})` : ''}
          </Typography>
          {(shift.predecessorDateSigned || shift.predecessorValue != null) && (
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              {shift.predecessorDateSigned ? `Signed ${formatDate(shift.predecessorDateSigned)}` : ''}
              {shift.predecessorDateSigned && shift.predecessorValue != null ? ' — ' : ''}
              {shift.predecessorValue != null ? formatCurrency(shift.predecessorValue) : ''}
            </Typography>
          )}
        </Box>
      )}
    </Alert>
  );
}

// ---------------------------------------------------------------------------
// Competition Level Card
// ---------------------------------------------------------------------------

const competitionLevelColors: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  Low: 'success',
  Moderate: 'warning',
  High: 'error',
  'Very High': 'error',
};

function CompetitionLevelCard({ landscape }: { landscape: CompetitiveLandscapeDto }) {
  const chipColor = competitionLevelColors[landscape.competitionLevel] ?? 'default';

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
      <Typography variant="subtitle2" sx={{ mb: 2 }}>
        Competition Level
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <Chip
          label={landscape.competitionLevel}
          color={chipColor}
          sx={{ fontWeight: 600, fontSize: '0.875rem' }}
        />
        <Typography variant="body2" sx={{
          color: "text.secondary"
        }}>
          {landscape.distinctVendorCount} distinct vendors in scope
        </Typography>
        {landscape.fallbackScope === 'NAICS' && (
          <Tooltip title="No agency-scoped data available; showing NAICS-wide competition level">
            <Chip label="NAICS-wide scope" size="small" variant="outlined" />
          </Tooltip>
        )}
      </Box>
      <Box sx={{ mt: 2 }}>
        <KeyFactsGrid
          facts={[
            { label: 'Agency Avg Award', value: formatCurrency(landscape.agencyAverageAwardValue) },
            { label: 'Scoped Avg Award', value: formatCurrency(landscape.averageAwardValue) },
            { label: 'Total Contracts (Scoped)', value: formatNumber(landscape.totalContracts) },
            { label: 'Total Value (Scoped)', value: formatCurrency(landscape.totalValue) },
          ]}
          columns={2}
        />
      </Box>
    </Paper>
  );
}

// ---------------------------------------------------------------------------
// Likely Competitors Table
// ---------------------------------------------------------------------------

function LikelyCompetitorsTable({ competitors }: { competitors: LikelyCompetitorDto[] }) {
  if (competitors.length === 0) return null;

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Likely Competitors
      </Typography>
      <Typography
        variant="body2"
        sx={{
          color: "text.secondary",
          mb: 1
        }}>
        Based on recent awards to the same agency in this NAICS code.
      </Typography>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Vendor</TableCell>
              <TableCell align="right">Contracts</TableCell>
              <TableCell align="right">Total Value</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {competitors.map((c) => (
              <TableRow key={c.ueiSam ?? c.vendorName}>
                <TableCell>{c.vendorName}</TableCell>
                <TableCell align="right">{formatNumber(c.contractCount)}</TableCell>
                <TableCell align="right">{formatCurrency(c.totalValue)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Main Tab
// ---------------------------------------------------------------------------

export default function CompetitiveIntelTab({ opp }: { opp: OpportunityDetail }) {
  // Set-Aside Shift
  const {
    data: shiftData,
    isLoading: shiftLoading,
    isError: shiftError,
  } = useQuery({
    queryKey: queryKeys.opportunities.setAsideShift(opp.noticeId),
    queryFn: () => getSetAsideShift(opp.noticeId),
    staleTime: 5 * 60 * 1000,
  });

  // Competitive Landscape (new — scoped to agency + NAICS + set-aside)
  const {
    data: landscape,
    isLoading: landscapeLoading,
    isError: landscapeError,
  } = useQuery({
    queryKey: queryKeys.opportunities.competitiveLandscape(opp.noticeId),
    queryFn: () => getCompetitiveLandscape(opp.noticeId),
    staleTime: 5 * 60 * 1000,
  });

  // Incumbent Analysis
  const {
    data: incumbent,
    isLoading: incumbentLoading,
    isError: incumbentError,
  } = useQuery({
    queryKey: queryKeys.opportunities.incumbent(opp.noticeId),
    queryFn: () => getIncumbentAnalysis(opp.noticeId),
    staleTime: 5 * 60 * 1000,
  });

  // NAICS-wide market share (existing — kept for context)
  const {
    data: marketShare,
    isLoading: marketLoading,
    isError: marketError,
  } = useQuery({
    queryKey: queryKeys.awards.marketShare(opp.naicsCode ?? ''),
    queryFn: () => getIntelMarketShare(opp.naicsCode!, 3, 10),
    staleTime: 10 * 60 * 1000,
    enabled: !!opp.naicsCode,
  });

  // NAICS Set-Aside Trends
  const {
    data: trendData,
    isLoading: trendLoading,
    isError: trendError,
  } = useQuery({
    queryKey: queryKeys.awards.setAsideTrends(opp.naicsCode ?? ''),
    queryFn: () => getSetAsideTrends(opp.naicsCode!),
    staleTime: 10 * 60 * 1000,
    enabled: !!opp.naicsCode,
  });

  // Incumbent Vulnerability Score
  const {
    data: ivsData,
    isLoading: ivsLoading,
  } = useQuery({
    queryKey: queryKeys.opportunities.ivs(opp.noticeId),
    queryFn: () => getIvs(opp.noticeId),
    enabled: !!opp.noticeId,
    staleTime: 5 * 60 * 1000,
  });

  // Competitor Strength Index
  const {
    data: csiData,
    isLoading: csiLoading,
  } = useQuery({
    queryKey: queryKeys.opportunities.competitors(opp.noticeId),
    queryFn: () => getOpportunityCompetitors(opp.noticeId),
    enabled: !!opp.noticeId,
    staleTime: 5 * 60 * 1000,
  });

  return (
    <Box>
      {/* 1. Competition Level (from competitive landscape endpoint) */}
      {landscapeLoading ? (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <LoadingState message="Analyzing competitive landscape..." />
        </Paper>
      ) : landscapeError || !landscape ? (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <ErrorState
            title="Competitive landscape unavailable"
            message="Could not load scoped competition data for this opportunity."
          />
        </Paper>
      ) : (
        <CompetitionLevelCard landscape={landscape} />
      )}
      {/* 2. Set-Aside Shift Indicator */}
      {shiftLoading ? (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <LoadingState message="Checking set-aside shift..." />
        </Paper>
      ) : shiftError ? (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <ErrorState
            title="Set-aside shift unavailable"
            message="Could not load set-aside shift data for this opportunity."
          />
        </Paper>
      ) : shiftData ? (
        <SetAsideShiftCard shift={shiftData} />
      ) : null}
      {/* 3. Incumbent Analysis */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Incumbent Analysis
        </Typography>
        {incumbentLoading ? (
          <LoadingState message="Analyzing incumbent..." />
        ) : incumbentError || !incumbent ? (
          <ErrorState
            title="Incumbent analysis unavailable"
            message="Could not load incumbent analysis for this opportunity."
          />
        ) : !incumbent.hasIncumbent && !incumbent.isLikelyIncumbent ? (
          <Box>
            <EmptyState
              title="No incumbent identified"
              message="This appears to be a new requirement with no prior contract holder."
            />
            {/* Show likely competitors even when no incumbent */}
            {incumbent.likelyCompetitors && incumbent.likelyCompetitors.length > 0 && (
              <LikelyCompetitorsTable competitors={incumbent.likelyCompetitors} />
            )}
          </Box>
        ) : (
          <Box>
            <KeyFactsGrid
              facts={[
                { label: 'Incumbent', value: incumbent.incumbentName ?? '--' },
                { label: 'UEI', value: incumbent.incumbentUei ?? '--' },
                { label: 'Contract ID', value: incumbent.contractId ?? '--' },
                { label: 'Contract Value (Ceiling)', value: formatCurrency(incumbent.contractValue) },
                {
                  label: 'Period',
                  value:
                    incumbent.periodStart || incumbent.periodEnd
                      ? `${formatDate(incumbent.periodStart)} - ${formatDate(incumbent.periodEnd)}`
                      : '--',
                },
                { label: 'Monthly Burn Rate', value: formatCurrency(incumbent.monthlyBurnRate) },
                { label: 'Percent Spent', value: formatPercent(incumbent.percentSpent) },
                { label: 'Registration Status', value: incumbent.registrationStatus ?? '--' },
                { label: 'Consecutive Wins', value: formatNumber(incumbent.consecutiveWins) },
                {
                  label: 'Excluded',
                  value: incumbent.isExcluded
                    ? `Yes - ${incumbent.exclusionType ?? 'Unknown type'}`
                    : 'No',
                },
              ]}
              columns={2}
            />

            {/* Months remaining highlight */}
            {incumbent.monthsRemaining != null && (
              <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <Chip
                  label={`${incumbent.monthsRemaining} months remaining`}
                  color={incumbent.monthsRemaining <= 6 ? 'warning' : 'default'}
                  variant="outlined"
                  sx={{ fontWeight: 600 }}
                />
              </Box>
            )}

            {/* Vulnerability Signals */}
            {incumbent.vulnerabilitySignals.length > 0 && (
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Vulnerability Signals
                </Typography>
                <VulnerabilitySignals signals={incumbent.vulnerabilitySignals} />
              </Box>
            )}

            {/* Likely competitors when incumbent is estimated */}
            {incumbent.likelyCompetitors && incumbent.likelyCompetitors.length > 0 && (
              <LikelyCompetitorsTable competitors={incumbent.likelyCompetitors} />
            )}
          </Box>
        )}
      </Paper>
      {/* 3a. Incumbent Vulnerability Score */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Incumbent Vulnerability Score
        </Typography>
        {ivsLoading ? (
          <Box>
            <Skeleton variant="rectangular" height={40} sx={{ mb: 2 }} />
            <Skeleton variant="rectangular" height={120} />
          </Box>
        ) : !ivsData ? (
          <Typography variant="body2" sx={{
            color: "text.secondary"
          }}>
            No incumbent vulnerability data available.
          </Typography>
        ) : (
          <Box>
            {/* Score display */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
              <Typography variant="h3" sx={{ fontWeight: 700 }}>
                {ivsData.score}
              </Typography>
              <Box>
                <Chip
                  label={ivsData.category}
                  size="small"
                  color={
                    ivsData.category === 'HighlyVulnerable' ? 'error'
                    : ivsData.category === 'Vulnerable' ? 'warning'
                    : ivsData.category === 'Stable' ? 'info'
                    : 'success'
                  }
                  sx={{ fontWeight: 600, mr: 1 }}
                />
                <Chip
                  label={`${ivsData.confidence} confidence`}
                  size="small"
                  variant="outlined"
                />
              </Box>
              <Typography variant="body2" sx={{
                color: "text.secondary"
              }}>
                Data completeness: {ivsData.dataCompletenessPercent}%
              </Typography>
            </Box>

            {/* Factor breakdown */}
            {ivsData.factors.length > 0 && (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Factor</TableCell>
                      <TableCell align="right">Score</TableCell>
                      <TableCell align="right">Weight</TableCell>
                      <TableCell align="right">Weighted</TableCell>
                      <TableCell>Detail</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {ivsData.factors.map((f) => (
                      <TableRow key={f.name} sx={{ opacity: f.hadRealData ? 1 : 0.6 }}>
                        <TableCell>{f.name}</TableCell>
                        <TableCell align="right">{f.score}</TableCell>
                        <TableCell align="right">{(f.weight * 100).toFixed(0)}%</TableCell>
                        <TableCell align="right">{f.weightedScore.toFixed(1)}</TableCell>
                        <TableCell sx={{ fontSize: '0.8rem', color: 'text.secondary' }}>{f.detail}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {/* Vulnerability signals */}
            {ivsData.signals.length > 0 && (
              <Box sx={{ mt: 2 }}>
                {ivsData.signals.map((signal, idx) => (
                  <Alert key={idx} severity="info" variant="outlined" sx={{ mb: 1 }}>
                    {signal}
                  </Alert>
                ))}
              </Box>
            )}
          </Box>
        )}
      </Paper>
      {/* 3b. Scoped Top Competitors (from competitive landscape endpoint) */}
      {landscape && landscape.topVendors.length > 0 && (
        <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
          <MarketShareChart
            vendors={landscape.topVendors.map((v) => ({
              vendorName: v.vendorName,
              totalValue: v.totalValue,
              marketSharePercent: v.marketSharePercent,
              contractCount: v.contractCount,
            }))}
            title="Top Competitors (Scoped)"
          />
          {landscape.fallbackScope === 'NAICS' && (
            <Typography
              variant="caption"
              sx={{
                color: "text.secondary",
                mt: 1,
                display: 'block'
              }}>
              Showing NAICS-wide data — agency-scoped results had too few vendors.
            </Typography>
          )}
        </Paper>
      )}
      {/* 3c. Competitor Strength Index */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Competitor Strength Index
        </Typography>
        {csiLoading ? (
          <Box>
            <Skeleton variant="rectangular" height={40} sx={{ mb: 2 }} />
            <Skeleton variant="rectangular" height={160} />
          </Box>
        ) : !csiData || csiData.competitors.length === 0 ? (
          <Typography variant="body2" sx={{
            color: "text.secondary"
          }}>
            No competitor strength data available.
          </Typography>
        ) : (
          <Box>
            <Typography
              variant="body2"
              sx={{
                color: "text.secondary",
                mb: 2
              }}>
              {csiData.totalCompetitorsFound} competitors found
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Vendor</TableCell>
                    <TableCell align="right">CSI</TableCell>
                    <TableCell align="center">Strength</TableCell>
                    <TableCell align="right">Contracts</TableCell>
                    <TableCell align="right">Value</TableCell>
                    <TableCell align="right">Share</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {csiData.competitors.map((c) => (
                    <Tooltip
                      key={c.vendorUei}
                      title={
                        c.factors.map((f) => `${f.name}: ${f.score} (${(f.weight * 100).toFixed(0)}%)`).join('\n')
                      }
                    >
                      <TableRow hover>
                        <TableCell>{c.vendorName}</TableCell>
                        <TableCell align="right">{c.csiScore}</TableCell>
                        <TableCell align="center">
                          <Chip
                            label={c.category}
                            size="small"
                            color={
                              c.category === 'Dominant' ? 'error'
                              : c.category === 'Strong' ? 'warning'
                              : c.category === 'Moderate' ? 'info'
                              : 'success'
                            }
                          />
                        </TableCell>
                        <TableCell align="right">{formatNumber(c.contractCount)}</TableCell>
                        <TableCell align="right">{formatCurrency(c.totalValue)}</TableCell>
                        <TableCell align="right">{c.marketSharePercent.toFixed(1)}%</TableCell>
                      </TableRow>
                    </Tooltip>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}
      </Paper>
      {/* 4. NAICS-wide Market Context */}
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          NAICS Market Context{opp.naicsCode ? ` — ${opp.naicsCode}` : ''}
        </Typography>
        {!opp.naicsCode ? (
          <EmptyState
            title="No NAICS Code"
            message="Cannot show market landscape without a NAICS code."
          />
        ) : marketLoading ? (
          <LoadingState message="Loading market data..." />
        ) : marketError || !marketShare ? (
          <ErrorState
            title="Market data unavailable"
            message="Could not load market share data."
          />
        ) : (
          <Box>
            <MarketShareChart
              vendors={marketShare.topVendors.map((v) => ({
                vendorName: v.vendorName,
                totalValue: v.totalValue,
                marketSharePercent: v.marketSharePercent,
                contractCount: v.contractCount,
              }))}
              title={`Top Vendors — NAICS ${marketShare.naicsCode}`}
            />

            {/* Summary stats */}
            <Box sx={{ mt: 3 }}>
              <KeyFactsGrid
                facts={[
                  { label: 'Total Contracts', value: formatNumber(marketShare.totalContracts) },
                  { label: 'Total Market Value', value: formatCurrency(marketShare.totalValue) },
                  { label: 'Average Award Value', value: formatCurrency(marketShare.averageAwardValue) },
                  { label: 'Years Analyzed', value: String(marketShare.yearsAnalyzed) },
                ]}
                columns={2}
              />
            </Box>
          </Box>
        )}
      </Paper>
      {/* 5. NAICS Set-Aside Trend Chart */}
      {opp.naicsCode && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 2 }}>
            Set-Aside Trends — NAICS {opp.naicsCode}
          </Typography>
          {trendLoading ? (
            <LoadingState message="Loading set-aside trends..." />
          ) : trendError ? (
            <ErrorState
              title="Trend data unavailable"
              message="Could not load set-aside trend data for this NAICS code."
            />
          ) : trendData && trendData.length > 0 ? (
            <SetAsideTrendChart
              trends={trendData}
              title={`Set-Aside Distribution — NAICS ${opp.naicsCode}`}
            />
          ) : (
            <EmptyState
              title="No trend data"
              message="No historical set-aside trend data available for this NAICS code."
            />
          )}
        </Paper>
      )}
      {/* 6. Partner Compatibility */}
      <Box sx={{ mt: 3 }}>
        <PartnerCompatibilitySection noticeId={opp.noticeId} />
      </Box>
      {/* 7. Open Door Primes */}
      {opp.naicsCode && (
        <Box sx={{ mt: 3 }}>
          <OpenDoorSection naicsCode={opp.naicsCode} />
        </Box>
      )}
    </Box>
  );
}
