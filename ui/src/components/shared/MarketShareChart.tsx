import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { BarChart } from '@mui/x-charts/BarChart';
import { EmptyState } from '@/components/shared/EmptyState';
import { formatCurrency } from '@/utils/formatters';

interface MarketShareVendor {
  vendorName: string | null;
  totalValue: number;
  marketSharePercent: number;
  contractCount: number;
}

interface MarketShareChartProps {
  vendors: MarketShareVendor[];
  title?: string;
}

export default function MarketShareChart({
  vendors,
  title = 'Market Share',
}: MarketShareChartProps) {
  if (vendors.length === 0) {
    return (
      <EmptyState
        title="No vendor data available"
        message="Market share data will appear here once vendor awards are loaded."
      />
    );
  }

  const dataset = vendors.map((v) => {
    const name = v.vendorName ?? 'Unknown';
    return {
      vendor: name.length > 30 ? name.slice(0, 27) + '...' : name,
      value: v.totalValue,
    };
  });

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        {title}
      </Typography>
      <Box sx={{ width: '100%', height: Math.max(300, vendors.length * 40) }}>
        <BarChart
          dataset={dataset}
          yAxis={[{ scaleType: 'band', dataKey: 'vendor' }]}
          xAxis={[
            {
              valueFormatter: (v: number) => formatCurrency(v) ?? '',
            },
          ]}
          series={[
            {
              dataKey: 'value',
              label: 'Award Value',
              valueFormatter: (v) =>
                formatCurrency(v as number | null) ?? '',
            },
          ]}
          layout="horizontal"
          margin={{ left: 200 }}
        />
      </Box>
    </Box>
  );
}
