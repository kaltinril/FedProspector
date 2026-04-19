import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CircularProgress from '@mui/material/CircularProgress';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Typography from '@mui/material/Typography';
import RefreshIcon from '@mui/icons-material/Refresh';

import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { useHierarchyRefresh, useHierarchyRefreshStatus } from '@/queries/useHierarchy';
import { formatDateTime } from '@/utils/dateFormatters';
import type { HierarchyRefreshRequest } from '@/types/api';

export function HierarchyRefreshPanel() {
  const [apiKey, setApiKey] = useState<1 | 2>(2);
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    level: HierarchyRefreshRequest['level'];
    title: string;
    message: string;
    severity: 'info' | 'warning' | 'error';
  }>({ open: false, level: 'hierarchy', title: '', message: '', severity: 'info' });

  const refreshMutation = useHierarchyRefresh();
  const { data: status } = useHierarchyRefreshStatus(refreshMutation.isPending);

  const isRunning = status?.isRunning ?? false;

  function openConfirm(
    level: HierarchyRefreshRequest['level'],
    title: string,
    message: string,
    severity: 'info' | 'warning' | 'error',
  ) {
    setConfirmDialog({ open: true, level, title, message, severity });
  }

  function handleConfirm() {
    refreshMutation.mutate({ level: confirmDialog.level, apiKey });
    setConfirmDialog((prev) => ({ ...prev, open: false }));
  }

  function handleCancel() {
    setConfirmDialog((prev) => ({ ...prev, open: false }));
  }

  return (
    <Card variant="outlined" sx={{ mb: 2 }}>
      <CardContent sx={{ py: 2, '&:last-child': { pb: 2 } }}>
        <Typography variant="subtitle2" gutterBottom>
          Hierarchy Data Refresh
        </Typography>

        {/* API key selector */}
        <Box sx={{ mb: 1.5 }}>
          <Typography variant="caption" sx={{
            color: "text.secondary"
          }}>
            API Key
          </Typography>
          <RadioGroup
            row
            value={apiKey}
            onChange={(e) => setApiKey(Number(e.target.value) as 1 | 2)}
          >
            <FormControlLabel
              value={1}
              control={<Radio size="small" />}
              label={
                <Typography variant="body2">
                  Key 1 <Typography component="span" variant="caption" sx={{
                  color: "text.secondary"
                }}>(10/day)</Typography>
                </Typography>
              }
            />
            <FormControlLabel
              value={2}
              control={<Radio size="small" />}
              label={
                <Typography variant="body2">
                  Key 2 <Typography component="span" variant="caption" sx={{
                  color: "text.secondary"
                }}>(1,000/day)</Typography>
                </Typography>
              }
            />
          </RadioGroup>
        </Box>

        {/* Refresh buttons */}
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 1.5 }}>
          <Button
            size="small"
            variant="outlined"
            startIcon={isRunning ? <CircularProgress size={16} /> : <RefreshIcon />}
            disabled={isRunning}
            onClick={() =>
              openConfirm(
                'hierarchy',
                'Refresh Hierarchy',
                'This will refresh departments and sub-tiers (levels 1-2). Continue?',
                'info',
              )
            }
          >
            Refresh Hierarchy
          </Button>
          <Button
            size="small"
            variant="outlined"
            startIcon={isRunning ? <CircularProgress size={16} /> : <RefreshIcon />}
            disabled={isRunning}
            onClick={() =>
              openConfirm(
                'offices',
                'Refresh Offices',
                'This will refresh all offices (level 3). This may use up to ~738 API calls. Continue?',
                'warning',
              )
            }
          >
            Refresh Offices
          </Button>
          <Button
            size="small"
            variant="outlined"
            color="error"
            startIcon={isRunning ? <CircularProgress size={16} /> : <RefreshIcon />}
            disabled={isRunning}
            onClick={() =>
              openConfirm(
                'full',
                'Full Refresh',
                'This will truncate and reload ALL hierarchy levels. This is a destructive operation. Are you sure?',
                'error',
              )
            }
          >
            Full Refresh
          </Button>
        </Box>

        {/* Status info */}
        {status && (
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" sx={{
                color: "text.secondary"
              }}>
                Last Refresh
              </Typography>
              <Typography variant="body2">
                {status.lastRefreshAt ? formatDateTime(status.lastRefreshAt) : 'Never'}
              </Typography>
            </Box>
            {status.lastRefreshRecordCount != null && (
              <Box>
                <Typography variant="caption" sx={{
                  color: "text.secondary"
                }}>
                  Records Loaded
                </Typography>
                <Typography variant="body2">
                  {status.lastRefreshRecordCount.toLocaleString()}
                </Typography>
              </Box>
            )}
            {status.levelsLoaded && status.levelsLoaded.length > 0 && (
              <Box>
                <Typography variant="caption" sx={{
                  color: "text.secondary"
                }}>
                  By Level
                </Typography>
                <Typography variant="body2">
                  {status.levelsLoaded.map((l) => `L${l.level}: ${l.count}`).join(', ')}
                </Typography>
              </Box>
            )}
          </Box>
        )}

        {isRunning && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
            <CircularProgress size={16} />
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              Refresh in progress...
            </Typography>
          </Box>
        )}
      </CardContent>
      <ConfirmDialog
        open={confirmDialog.open}
        title={confirmDialog.title}
        message={confirmDialog.message}
        severity={confirmDialog.severity}
        confirmText="Start Refresh"
        onConfirm={handleConfirm}
        onCancel={handleCancel}
        loading={refreshMutation.isPending}
      />
    </Card>
  );
}
