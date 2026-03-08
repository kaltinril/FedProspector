import { useQuery } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';

import { KeyFactsGrid } from '@/components/shared/KeyFactsGrid';
import VulnerabilitySignals from '@/components/shared/VulnerabilitySignals';
import MarketShareChart from '@/components/shared/MarketShareChart';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { getIncumbentAnalysis } from '@/api/opportunities';
import { getIntelMarketShare } from '@/api/awards';
import { queryKeys } from '@/queries/queryKeys';
import { formatCurrency, formatPercent, formatNumber } from '@/utils/formatters';
import { formatDate } from '@/utils/dateFormatters';
import type { OpportunityDetail } from '@/types/api';

export default function CompetitiveIntelTab({ opp }: { opp: OpportunityDetail }) {
  const {
    data: incumbent,
    isLoading: incumbentLoading,
    isError: incumbentError,
  } = useQuery({
    queryKey: queryKeys.opportunities.incumbent(opp.noticeId),
    queryFn: () => getIncumbentAnalysis(opp.noticeId),
    staleTime: 5 * 60 * 1000,
  });

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

  return (
    <Box>
      {/* Incumbent Analysis */}
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
        ) : !incumbent.hasIncumbent ? (
          <EmptyState
            title="No incumbent identified"
            message="This appears to be a new requirement with no prior contract holder."
          />
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
          </Box>
        )}
      </Paper>

      {/* Market Landscape */}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 2 }}>
          Market Landscape{opp.naicsCode ? ` — NAICS ${opp.naicsCode}` : ''}
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
    </Box>
  );
}
