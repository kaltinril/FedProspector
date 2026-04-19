import { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Alert from '@mui/material/Alert';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import RefreshIcon from '@mui/icons-material/Refresh';
import Tooltip from '@mui/material/Tooltip';

import { useEtlStatus } from '@/queries/useAdmin';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { formatDateTime, formatRelative } from '@/utils/dateFormatters';
import { formatNumber } from '@/utils/formatters';
import type { RecentErrorDto } from '@/types/api';

const STATUS_CHIP_MAP: Record<string, 'success' | 'warning' | 'error' | 'default'> = {
  OK: 'success',
  WARNING: 'warning',
  STALE: 'error',
  NEVER: 'default',
};

export default function EtlStatusTab() {
  const { data, isLoading, isError, refetch } = useEtlStatus();
  const [errorsExpanded, setErrorsExpanded] = useState(true);

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => refetch()} />;

  return (
    <Box>
      {/* Alerts */}
      {data.alerts.length > 0 && (
        <Box sx={{ mb: 3 }}>
          {data.alerts.map((alert, idx) => (
            <Alert key={idx} severity="warning" sx={{ mb: 1 }}>
              {alert}
            </Alert>
          ))}
        </Box>
      )}
      {/* Source Status Table */}
      <Paper sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 2 }}>
          <Typography variant="h6">Source Status</Typography>
          <Tooltip title="Refresh">
            <IconButton size="small" onClick={() => refetch()}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Source</TableCell>
                <TableCell>Last Load</TableCell>
                <TableCell align="right">Hours Since</TableCell>
                <TableCell align="right">Threshold</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Records</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.sources.map((src) => (
                <TableRow key={src.sourceSystem}>
                  <TableCell>
                    <Typography variant="body2" sx={{
                      fontWeight: 500
                    }}>
                      {src.label}
                    </Typography>
                    <Typography variant="caption" sx={{
                      color: "text.secondary"
                    }}>
                      {src.sourceSystem}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {src.lastLoadAt ? (
                      <Tooltip title={formatDateTime(src.lastLoadAt)}>
                        <span>{formatRelative(src.lastLoadAt)}</span>
                      </Tooltip>
                    ) : (
                      '--'
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {src.hoursSinceLoad != null ? src.hoursSinceLoad.toFixed(1) : '--'}
                  </TableCell>
                  <TableCell align="right">{src.thresholdHours}h</TableCell>
                  <TableCell>
                    <Chip
                      label={src.status}
                      color={STATUS_CHIP_MAP[src.status] ?? 'default'}
                      size="small"
                    />
                  </TableCell>
                  <TableCell align="right">{formatNumber(src.recordsProcessed)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
      {/* API Usage */}
      {data.apiUsage.length > 0 && (
        <Paper sx={{ mb: 3, p: 2 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>
            API Usage
          </Typography>
          {data.apiUsage.map((usage) => {
            const pct = usage.maxRequests > 0 ? (usage.requestsMade / usage.maxRequests) * 100 : 0;
            const barColor = pct > 90 ? 'error' : pct > 70 ? 'warning' : 'primary';
            return (
              <Box key={usage.sourceSystem} sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                  <Typography variant="body2" sx={{
                    fontWeight: 500
                  }}>
                    {usage.sourceSystem}
                  </Typography>
                  <Typography variant="body2" sx={{
                    color: "text.secondary"
                  }}>
                    {formatNumber(usage.requestsMade)} / {formatNumber(usage.maxRequests)}
                    {' '}({formatNumber(usage.remaining)} remaining)
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(pct, 100)}
                  color={barColor}
                  sx={{ height: 8, borderRadius: 1 }}
                />
                {usage.lastRequestAt && (
                  <Typography variant="caption" sx={{
                    color: "text.secondary"
                  }}>
                    Last request: {formatRelative(usage.lastRequestAt)}
                  </Typography>
                )}
              </Box>
            );
          })}
        </Paper>
      )}
      {/* Recent Errors */}
      {data.recentErrors.length > 0 && (
        <Paper sx={{ p: 2 }}>
          <Box
            sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
            onClick={() => setErrorsExpanded(!errorsExpanded)}
          >
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              Recent Errors ({data.recentErrors.length})
            </Typography>
            <IconButton size="small">
              {errorsExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </IconButton>
          </Box>
          <Collapse in={errorsExpanded}>
            <Box sx={{ mt: 1 }}>
              {data.recentErrors.map((err: RecentErrorDto, idx: number) => (
                <Alert key={idx} severity="error" sx={{ mb: 1 }}>
                  <Typography variant="body2" sx={{
                    fontWeight: 500
                  }}>
                    {err.sourceSystem}
                    {err.loadType ? ` - ${err.loadType}` : ''}
                  </Typography>
                  <Typography variant="caption" sx={{
                    color: "text.secondary"
                  }}>
                    {formatDateTime(err.startedAt)}
                  </Typography>
                  {err.errorMessage && (
                    <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: 'pre-wrap' }}>
                      {err.errorMessage}
                    </Typography>
                  )}
                </Alert>
              ))}
            </Box>
          </Collapse>
        </Paper>
      )}
    </Box>
  );
}
