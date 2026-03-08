import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSnackbar } from 'notistack';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import IconButton from '@mui/material/IconButton';
import MenuItem from '@mui/material/MenuItem';
import Pagination from '@mui/material/Pagination';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import CheckCircleOutlined from '@mui/icons-material/CheckCircleOutlined';
import DoneOutlined from '@mui/icons-material/DoneOutlined';
import NotificationsOutlined from '@mui/icons-material/NotificationsOutlined';
import ScheduleOutlined from '@mui/icons-material/ScheduleOutlined';
import SearchOutlined from '@mui/icons-material/SearchOutlined';
import SwapHorizOutlined from '@mui/icons-material/SwapHorizOutlined';
import TrendingUpOutlined from '@mui/icons-material/TrendingUpOutlined';

import { PageHeader } from '@/components/shared/PageHeader';
import { ErrorState } from '@/components/shared/ErrorState';
import { LoadingState } from '@/components/shared/LoadingState';
import { useNotifications, useMarkRead, useMarkAllRead } from '@/queries/useNotifications';
import { formatRelative } from '@/utils/dateFormatters';
import type { NotificationDto, NotificationListParams } from '@/types/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NOTIFICATION_ICONS: Record<string, React.ReactElement> = {
  'new_match': <SearchOutlined color="primary" />,
  'SEARCH_RESULTS': <SearchOutlined color="primary" />,
  'deadline_approaching': <ScheduleOutlined color="warning" />,
  'status_changed': <SwapHorizOutlined color="info" />,
  'score_recalculated': <TrendingUpOutlined color="success" />,
};

const TYPE_FILTER_OPTIONS = [
  { value: '', label: 'All Types' },
  { value: 'SEARCH_RESULTS', label: 'Search Results' },
  { value: 'new_match', label: 'New Match' },
  { value: 'deadline_approaching', label: 'Deadline Approaching' },
  { value: 'status_changed', label: 'Status Changed' },
  { value: 'score_recalculated', label: 'Score Recalculated' },
];

const DEFAULT_PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getIcon(type: string): React.ReactElement {
  return NOTIFICATION_ICONS[type] ?? <NotificationsOutlined color="action" />;
}

function getEntityRoute(entityType: string | null | undefined, entityId: string | null | undefined): string | null {
  if (!entityType || !entityId) return null;
  switch (entityType) {
    case 'opportunity':
      return `/opportunities/${encodeURIComponent(entityId)}`;
    case 'award':
      return `/awards/${encodeURIComponent(entityId)}`;
    case 'entity':
      return `/entities/${encodeURIComponent(entityId)}`;
    case 'prospect':
      return `/prospects/${encodeURIComponent(entityId)}`;
    case 'SAVED_SEARCH':
      return '/saved-searches';
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function NotificationCenterPage() {
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();

  const [unreadOnly, setUnreadOnly] = useState(false);
  const [typeFilter, setTypeFilter] = useState('');
  const [page, setPage] = useState(1);

  const params: NotificationListParams = {
    unreadOnly: unreadOnly || undefined,
    type: typeFilter || undefined,
    page,
    pageSize: DEFAULT_PAGE_SIZE,
  };

  const { data, isLoading, isError, refetch } = useNotifications(params);
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();

  const notifications = data?.notifications;

  const handleMarkRead = useCallback(
    (e: React.MouseEvent, id: number) => {
      e.stopPropagation();
      markRead.mutate(id, {
        onError: () => enqueueSnackbar('Failed to mark as read', { variant: 'error' }),
      });
    },
    [markRead, enqueueSnackbar],
  );

  const handleMarkAllRead = useCallback(() => {
    markAllRead.mutate(undefined, {
      onSuccess: () => enqueueSnackbar('All notifications marked as read', { variant: 'success' }),
      onError: () => enqueueSnackbar('Failed to mark all as read', { variant: 'error' }),
    });
  }, [markAllRead, enqueueSnackbar]);

  const handleCardClick = useCallback(
    (n: NotificationDto) => {
      // Mark as read when clicking
      if (!n.isRead) {
        markRead.mutate(n.notificationId);
      }
      const route = getEntityRoute(n.entityType, n.entityId);
      if (route) navigate(route);
    },
    [markRead, navigate],
  );

  const handlePageChange = useCallback((_: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
  }, []);

  // Reset page to 1 when filters change
  const handleUnreadToggle = useCallback((_: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
    setUnreadOnly(checked);
    setPage(1);
  }, []);

  const handleTypeChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setTypeFilter(e.target.value);
    setPage(1);
  }, []);

  // ------ Error state ------
  if (isError) {
    return (
      <Box>
        <PageHeader title="Notifications" />
        <ErrorState
          title="Failed to load notifications"
          message="Could not retrieve your notifications. Please try again."
          onRetry={() => refetch()}
        />
      </Box>
    );
  }

  return (
    <Box>
      <PageHeader
        title="Notifications"
        actions={
          <Button
            variant="outlined"
            onClick={handleMarkAllRead}
            disabled={markAllRead.isPending || (data?.unreadCount ?? 0) === 0}
          >
            Mark all as read
          </Button>
        }
      />

      {/* Filter bar */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <FormControlLabel
          control={<Switch checked={unreadOnly} onChange={handleUnreadToggle} />}
          label="Unread only"
        />
        <TextField
          select
          size="small"
          label="Type"
          value={typeFilter}
          onChange={handleTypeChange}
          sx={{ minWidth: 200 }}
        >
          {TYPE_FILTER_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              {opt.label}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      {/* Loading state */}
      {isLoading && <LoadingState message="Loading notifications..." />}

      {/* Empty state */}
      {!isLoading && notifications && notifications.items.length === 0 && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            py: 8,
          }}
        >
          <CheckCircleOutlined sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            You're all caught up!
          </Typography>
        </Box>
      )}

      {/* Notification feed */}
      {!isLoading && notifications && notifications.items.length > 0 && (
        <Stack spacing={1}>
          {notifications.items.map((n) => (
            <Paper
              key={n.notificationId}
              elevation={0}
              onClick={() => handleCardClick(n)}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                p: 2,
                cursor: getEntityRoute(n.entityType, n.entityId) ? 'pointer' : 'default',
                borderLeft: n.isRead ? '3px solid transparent' : '3px solid',
                borderLeftColor: n.isRead ? 'transparent' : 'primary.main',
                bgcolor: n.isRead ? 'background.paper' : 'action.hover',
                '&:hover': {
                  bgcolor: 'action.selected',
                },
              }}
            >
              {/* Icon */}
              <Box sx={{ display: 'flex', flexShrink: 0 }}>
                {getIcon(n.notificationType)}
              </Box>

              {/* Content */}
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="subtitle2" noWrap>
                  {n.title}
                </Typography>
                {n.message && (
                  <Typography variant="body2" color="text.secondary" noWrap>
                    {n.message}
                  </Typography>
                )}
                <Typography variant="caption" color="text.disabled">
                  {formatRelative(n.createdAt)}
                </Typography>
              </Box>

              {/* Read indicator + action */}
              <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                {!n.isRead && (
                  <IconButton
                    size="small"
                    title="Mark as read"
                    onClick={(e) => handleMarkRead(e, n.notificationId)}
                    disabled={markRead.isPending}
                  >
                    <DoneOutlined fontSize="small" />
                  </IconButton>
                )}
                {!n.isRead && (
                  <Box
                    sx={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      bgcolor: 'primary.main',
                      ml: 1,
                    }}
                  />
                )}
              </Box>
            </Paper>
          ))}

          {/* Pagination */}
          {notifications.totalPages > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', pt: 2 }}>
              <Pagination
                count={notifications.totalPages}
                page={notifications.page}
                onChange={handlePageChange}
                color="primary"
              />
            </Box>
          )}
        </Stack>
      )}
    </Box>
  );
}
