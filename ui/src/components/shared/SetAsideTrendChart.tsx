import { useMemo } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { BarChart } from '@mui/x-charts/BarChart';
import { EmptyState } from '@/components/shared/EmptyState';
import { formatNumber } from '@/utils/formatters';
import type { SetAsideTrendDto } from '@/types/api';

// Deterministic color palette for set-aside categories
const CATEGORY_COLORS: Record<string, string> = {
  '8(a)': '#1976d2',
  'WOSB': '#9c27b0',
  'EDWOSB': '#7b1fa2',
  'SDVOSB': '#2e7d32',
  'HUBZone': '#ed6c02',
  'Small Business': '#0288d1',
  'Full & Open': '#757575',
  'Other': '#546e7a',
};

const FALLBACK_COLORS = [
  '#1976d2', '#9c27b0', '#2e7d32', '#ed6c02', '#d32f2f',
  '#0288d1', '#7b1fa2', '#f57c00', '#388e3c', '#5d4037',
];

interface SetAsideTrendChartProps {
  trends: SetAsideTrendDto[];
  title?: string;
}

export default function SetAsideTrendChart({
  trends,
  title = 'Set-Aside Trends by Fiscal Year',
}: SetAsideTrendChartProps) {
  const { dataset, series, categories } = useMemo(() => {
    if (trends.length === 0) return { dataset: [], series: [], categories: [] };

    // Get unique fiscal years and categories
    const yearsSet = new Set<number>();
    const categoriesSet = new Set<string>();
    for (const t of trends) {
      yearsSet.add(t.fiscalYear);
      categoriesSet.add(t.setAsideCategory ?? t.setAsideType ?? 'Unknown');
    }

    const sortedYears = [...yearsSet].sort((a, b) => a - b);
    const sortedCategories = [...categoriesSet].sort();

    // Build dataset: one row per fiscal year, one key per category
    const ds = sortedYears.map((fy) => {
      const row: Record<string, string | number> = { year: String(fy) };
      for (const cat of sortedCategories) {
        const match = trends.find(
          (t) =>
            t.fiscalYear === fy &&
            (t.setAsideCategory ?? t.setAsideType ?? 'Unknown') === cat,
        );
        row[cat] = match ? match.contractCount : 0;
      }
      return row;
    });

    // Build series: one per category
    let colorIdx = 0;
    const seriesList = sortedCategories.map((cat) => ({
      dataKey: cat,
      label: cat,
      stack: 'total',
      color: CATEGORY_COLORS[cat] ?? FALLBACK_COLORS[colorIdx++ % FALLBACK_COLORS.length],
      valueFormatter: (v: number | null) => formatNumber(v) + ' contracts',
    }));

    return { dataset: ds, series: seriesList, categories: sortedCategories };
  }, [trends]);

  if (trends.length === 0 || dataset.length === 0) {
    return (
      <EmptyState
        title="No trend data available"
        message="Set-aside trend data will appear here when historical award data is available for this NAICS code."
      />
    );
  }

  return (
    <Box>
      <Typography variant="h6" sx={{ mb: 2 }}>
        {title}
      </Typography>
      <Box sx={{ width: '100%', height: Math.max(300, categories.length * 20 + 200) }}>
        <BarChart
          dataset={dataset}
          xAxis={[{ scaleType: 'band', dataKey: 'year', label: 'Fiscal Year' }]}
          yAxis={[
            {
              label: 'Contract Count',
              valueFormatter: (v: number) => formatNumber(v),
            },
          ]}
          series={series}
          margin={{ bottom: 20 }}
        />
      </Box>
    </Box>
  );
}
