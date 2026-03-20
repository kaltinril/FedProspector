import { useState } from 'react';
import Box from '@mui/material/Box';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { BarChart } from '@mui/x-charts/BarChart';
import { EmptyState } from '@/components/shared/EmptyState';
import { formatCurrency, formatNumber, formatPercent } from '@/utils/formatters';

interface MarketShareVendor {
  vendorName: string | null;
  totalValue: number;
  marketSharePercent: number;
  contractCount: number;
}

type ViewMode = 'dollar' | 'count';

interface MarketShareChartProps {
  vendors: MarketShareVendor[];
  title?: string;
}

export default function MarketShareChart({
  vendors,
  title = 'Market Share',
}: MarketShareChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('dollar');

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
      count: v.contractCount,
      percent: v.marketSharePercent,
    };
  });

  const isDollar = viewMode === 'dollar';

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6">{title}</Typography>
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={(_e, val: ViewMode | null) => {
            if (val) setViewMode(val);
          }}
          size="small"
        >
          <ToggleButton value="dollar">By Dollar Value</ToggleButton>
          <ToggleButton value="count">By Contract Count</ToggleButton>
        </ToggleButtonGroup>
      </Box>
      <Box sx={{ width: '100%', height: Math.max(300, vendors.length * 40) }}>
        <BarChart
          dataset={dataset}
          yAxis={[{ scaleType: 'band', dataKey: 'vendor' }]}
          xAxis={[
            {
              valueFormatter: isDollar
                ? (v: number) => formatCurrency(v) ?? ''
                : (v: number) => formatNumber(v),
            },
          ]}
          series={[
            {
              dataKey: isDollar ? 'value' : 'count',
              label: isDollar ? 'Award Value' : 'Contracts',
              valueFormatter: (v, { dataIndex }) => {
                const pct = dataIndex != null ? formatPercent(dataset[dataIndex].percent) : '';
                if (isDollar) {
                  const dollars = formatCurrency(v as number | null) ?? '';
                  return `${dollars} (${pct})`;
                }
                return `${formatNumber(v as number | null)} contracts (${pct})`;
              },
            },
          ]}
          layout="horizontal"
          margin={{ left: 200 }}
        />
      </Box>
    </Box>
  );
}
