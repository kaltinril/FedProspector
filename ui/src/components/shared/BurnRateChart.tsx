import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import { LineChart } from '@mui/x-charts/LineChart';
import { EmptyState } from '@/components/shared/EmptyState';
import { formatCurrency } from '@/utils/formatters';

interface MonthlySpend {
  month: string;
  amount: number;
}

interface BurnRateChartProps {
  data: MonthlySpend[];
  totalObligated?: number;
  baseAndAllOptions?: number;
  title?: string;
}

export function BurnRateChart({
  data,
  totalObligated,
  baseAndAllOptions,
  title = 'Monthly Spend',
}: BurnRateChartProps) {
  const showProgress =
    totalObligated != null && baseAndAllOptions != null && baseAndAllOptions > 0;
  const progressPct = showProgress
    ? Math.min((totalObligated / baseAndAllOptions) * 100, 100)
    : 0;

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        {title}
      </Typography>
      {showProgress && (
        <Box sx={{ mb: 3 }}>
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              mb: 0.5,
            }}
          >
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              Obligated: {formatCurrency(totalObligated)}
            </Typography>
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              Ceiling: {formatCurrency(baseAndAllOptions)}
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={progressPct}
            aria-label="Obligation progress"
            sx={{ height: 8, borderRadius: 1 }}
          />
          <Typography
            variant="caption"
            sx={{
              color: "text.secondary",
              mt: 0.5,
              display: 'block'
            }}>
            {progressPct.toFixed(1)}% of ceiling obligated
          </Typography>
        </Box>
      )}
      {data.length === 0 ? (
        <EmptyState
          title="No transaction data available"
          message="Spend data will appear here once transactions are recorded."
        />
      ) : (
        <LineChart
          xAxis={[{ data: data.map((d) => d.month), scaleType: 'band' }]}
          series={[
            {
              data: data.map((d) => d.amount),
              label: 'Amount',
              valueFormatter: (v) => formatCurrency(v),
              showMark: true,
            },
          ]}
          height={300}
        />
      )}
    </Box>
  );
}
