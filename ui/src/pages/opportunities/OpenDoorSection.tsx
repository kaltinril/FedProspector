import { useQuery } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Skeleton from '@mui/material/Skeleton';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { getOpenDoorPrimes } from '@/api/opportunities';
import { queryKeys } from '@/queries/queryKeys';
import type { OpenDoorFactorDto } from '@/types/api';

interface Props {
  naicsCode: string;
}

function categoryColor(category: string): 'success' | 'info' | 'warning' | 'error' {
  switch (category) {
    case 'Champion': return 'success';
    case 'Engaged': return 'info';
    case 'Minimal': return 'warning';
    default: return 'error';
  }
}

function factorTooltip(factors: OpenDoorFactorDto[]) {
  return factors.map(f => `${f.name}: ${f.score} (${(f.weight * 100).toFixed(0)}%)`).join('\n');
}

function formatCurrencyShort(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

export default function OpenDoorSection({ naicsCode }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.opportunities.openDoorPrimes(naicsCode),
    queryFn: () => getOpenDoorPrimes(naicsCode),
    enabled: !!naicsCode,
    staleTime: 10 * 60 * 1000,
  });

  if (isLoading) return <Skeleton variant="rounded" height={200} />;
  if (!data || data.primes.length === 0) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Open Door Primes</Typography>
          <Typography color="text.secondary">No prime contractor engagement data found for this NAICS code.</Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Open Door Primes</Typography>
          <Typography variant="body2" color="text.secondary">
            Primes most engaged with small business subs in NAICS {naicsCode}
          </Typography>
        </Box>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Prime Contractor</TableCell>
              <TableCell align="right">Score</TableCell>
              <TableCell align="center">Engagement</TableCell>
              <TableCell align="right">Subawards</TableCell>
              <TableCell align="right">Distinct Subs</TableCell>
              <TableCell align="right">Sub Value</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.primes.map((p) => (
              <Tooltip key={p.primeUei} title={factorTooltip(p.factors)} placement="left">
                <TableRow hover>
                  <TableCell>{p.primeName || p.primeUei}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 'bold' }}>{p.openDoorScore}</TableCell>
                  <TableCell align="center">
                    <Chip label={p.category} size="small" color={categoryColor(p.category)} />
                  </TableCell>
                  <TableCell align="right">{p.totalSubawards}</TableCell>
                  <TableCell align="right">{p.distinctSubs}</TableCell>
                  <TableCell align="right">{formatCurrencyShort(p.totalSubValue)}</TableCell>
                </TableRow>
              </Tooltip>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
