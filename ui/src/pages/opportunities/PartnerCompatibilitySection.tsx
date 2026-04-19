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
import { getPartners } from '@/api/opportunities';
import { queryKeys } from '@/queries/queryKeys';
import type { PcsFactorDto } from '@/types/api';

interface Props {
  noticeId: string;
}

function categoryColor(category: string): 'success' | 'info' | 'warning' | 'error' {
  switch (category) {
    case 'Ideal': return 'success';
    case 'Strong': return 'info';
    case 'Acceptable': return 'warning';
    default: return 'error';
  }
}

function factorTooltip(factors: PcsFactorDto[]) {
  return factors.map(f => `${f.name}: ${f.score} (${(f.weight * 100).toFixed(0)}%)`).join('\n');
}

export default function PartnerCompatibilitySection({ noticeId }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: queryKeys.opportunities.partners(noticeId),
    queryFn: () => getPartners(noticeId),
    enabled: !!noticeId,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) return <Skeleton variant="rounded" height={200} />;
  if (!data || data.partners.length === 0) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Potential Teaming Partners</Typography>
          <Typography sx={{
            color: "text.secondary"
          }}>No potential partners found based on subaward data for this opportunity.</Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">Potential Teaming Partners</Typography>
          <Chip label={`${data.totalPartnersFound} found`} size="small" />
        </Box>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Partner</TableCell>
              <TableCell align="right">PCS</TableCell>
              <TableCell align="center">Fit</TableCell>
              <TableCell align="right">Past Teaming</TableCell>
              <TableCell align="right">Agency Awards</TableCell>
              <TableCell align="center">Confidence</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.partners.map((p) => (
              <Tooltip key={p.partnerUei} title={factorTooltip(p.factors)} placement="left">
                <TableRow hover>
                  <TableCell>{p.partnerName || p.partnerUei}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 'bold' }}>{p.pcsScore}</TableCell>
                  <TableCell align="center">
                    <Chip label={p.category} size="small" color={categoryColor(p.category)} />
                  </TableCell>
                  <TableCell align="right">{p.pastTeamingCount}</TableCell>
                  <TableCell align="right">{p.agencyAwardCount}</TableCell>
                  <TableCell align="center">
                    <Chip
                      label={p.confidence[0]}
                      size="small"
                      variant="outlined"
                      color={p.confidence === 'High' ? 'success' : p.confidence === 'Medium' ? 'warning' : 'error'}
                      sx={{ minWidth: 24, height: 20, '& .MuiChip-label': { px: 0.5, fontSize: '0.7rem' } }}
                    />
                  </TableCell>
                </TableRow>
              </Tooltip>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
