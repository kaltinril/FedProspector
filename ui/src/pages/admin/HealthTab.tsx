import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import Chip from '@mui/material/Chip';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableRow from '@mui/material/TableRow';
import RefreshIcon from '@mui/icons-material/Refresh';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';

import { useHealth } from '@/queries/useAdmin';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';

const STATUS_COLOR_MAP: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  Healthy: 'success',
  healthy: 'success',
  Degraded: 'warning',
  degraded: 'warning',
  Unhealthy: 'error',
  unhealthy: 'error',
};

function statusColor(status: string): 'success' | 'warning' | 'error' | 'default' {
  return STATUS_COLOR_MAP[status] ?? 'default';
}

export default function HealthTab() {
  const { data, isLoading, isError, refetch } = useHealth();

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => refetch()} />;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3, gap: 1 }}>
        <Typography variant="h6">System Health</Typography>
        <Chip label={data.status} color={statusColor(data.status)} />
        <Tooltip title="Refresh">
          <IconButton size="small" onClick={() => refetch()}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Grid container spacing={3}>
        {/* Database Status */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Typography variant="subtitle1" fontWeight="bold">
                  Database
                </Typography>
                <Chip
                  label={data.database.status}
                  color={statusColor(data.database.status)}
                  size="small"
                />
              </Box>
              {data.database.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  {data.database.description}
                </Typography>
              )}
              {data.database.data && Object.keys(data.database.data).length > 0 && (
                <Table size="small">
                  <TableBody>
                    {Object.entries(data.database.data).map(([key, value]) => (
                      <TableRow key={key}>
                        <TableCell sx={{ fontWeight: 500, border: 0, pl: 0 }}>{key}</TableCell>
                        <TableCell sx={{ border: 0 }}>{String(value ?? '--')}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* ETL Freshness */}
        <Grid size={{ xs: 12, md: 6 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <Typography variant="subtitle1" fontWeight="bold">
                  ETL Freshness
                </Typography>
                <Chip
                  label={data.etlFreshness.status}
                  color={statusColor(data.etlFreshness.status)}
                  size="small"
                />
              </Box>
              {data.etlFreshness.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  {data.etlFreshness.description}
                </Typography>
              )}
              {data.etlFreshness.data && Object.keys(data.etlFreshness.data).length > 0 && (
                <Table size="small">
                  <TableBody>
                    {Object.entries(data.etlFreshness.data).map(([key, value]) => (
                      <TableRow key={key}>
                        <TableCell sx={{ fontWeight: 500, border: 0, pl: 0 }}>{key}</TableCell>
                        <TableCell sx={{ border: 0 }}>{String(value ?? '--')}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Additional Details */}
        {data.details && Object.keys(data.details).length > 0 && (
          <Grid size={{ xs: 12 }}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" fontWeight="bold" sx={{ mb: 2 }}>
                  Additional Details
                </Typography>
                <Table size="small">
                  <TableBody>
                    {Object.entries(data.details).map(([key, value]) => (
                      <TableRow key={key}>
                        <TableCell sx={{ fontWeight: 500, border: 0, pl: 0, width: '30%' }}>
                          {key}
                        </TableCell>
                        <TableCell sx={{ border: 0 }}>{String(value ?? '--')}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}
