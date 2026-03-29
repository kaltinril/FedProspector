import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Paper from '@mui/material/Paper';

import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { useHierarchyStats } from '@/queries/useHierarchy';
import { formatCurrency } from '@/utils/formatters';

interface OrgStatsCardsProps {
  fhOrgId: string;
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <Card variant="outlined">
      <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {label}
        </Typography>
        <Typography variant="h5" component="div">
          {value}
        </Typography>
      </CardContent>
    </Card>
  );
}

export function OrgStatsCards({ fhOrgId }: OrgStatsCardsProps) {
  const { data: stats, isLoading, isError, refetch } = useHierarchyStats(fhOrgId);

  if (isLoading) {
    return <LoadingState message="Loading statistics..." />;
  }

  if (isError || !stats) {
    return (
      <ErrorState
        title="Failed to load statistics"
        message="Could not retrieve statistics for this organization."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Summary cards */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
          gap: 2,
        }}
      >
        <StatCard label="Total Opportunities" value={stats.opportunityCount.toLocaleString()} />
        <StatCard label="Open Opportunities" value={stats.openOpportunityCount.toLocaleString()} />
        <StatCard label="Total Awards" value={stats.awardCount.toLocaleString()} />
        <StatCard label="Total Award Dollars" value={formatCurrency(stats.totalAwardDollars, true)} />
      </Box>

      {/* NAICS breakdown table */}
      {stats.topNaicsCodes && stats.topNaicsCodes.length > 0 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Top NAICS Codes
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>NAICS Code</TableCell>
                  <TableCell align="right">Count</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {stats.topNaicsCodes.map((item) => (
                  <TableRow key={item.code}>
                    <TableCell>{item.code}</TableCell>
                    <TableCell align="right">{item.count.toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* Set-aside breakdown table */}
      {stats.setAsideBreakdown && stats.setAsideBreakdown.length > 0 && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Set-Aside Distribution
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Set-Aside Type</TableCell>
                  <TableCell align="right">Count</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {stats.setAsideBreakdown.map((item) => (
                  <TableRow key={item.type}>
                    <TableCell>{item.type}</TableCell>
                    <TableCell align="right">{item.count.toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}
    </Box>
  );
}
