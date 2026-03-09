import { useState } from 'react';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import IconButton from '@mui/material/IconButton';
import Badge from '@mui/material/Badge';
import Avatar from '@mui/material/Avatar';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Divider from '@mui/material/Divider';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import ListItemIcon from '@mui/material/ListItemIcon';
import Popover from '@mui/material/Popover';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import Button from '@mui/material/Button';
import Brightness4 from '@mui/icons-material/Brightness4';
import Brightness7 from '@mui/icons-material/Brightness7';
import NotificationsOutlined from '@mui/icons-material/NotificationsOutlined';
import PersonOutlined from '@mui/icons-material/PersonOutlined';
import CorporateFareOutlined from '@mui/icons-material/CorporateFareOutlined';
import LogoutOutlined from '@mui/icons-material/LogoutOutlined';
import MenuIcon from '@mui/icons-material/Menu';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/auth/useAuth';
import { useThemeMode } from '@/theme/useThemeMode';
import { useUnreadCount, useNotifications, useMarkRead } from '@/queries/useNotifications';
import type { NotificationDto } from '@/types/api';
import { formatRelative } from '@/utils/dateFormatters';
import { Breadcrumb } from '@/components/layout/Breadcrumb';
import { SIDEBAR_WIDTH_EXPANDED, SIDEBAR_WIDTH_COLLAPSED } from '@/components/layout/Sidebar';

interface TopBarProps {
  sidebarCollapsed: boolean;
  onMobileMenuToggle: () => void;
}

export function TopBar({ sidebarCollapsed, onMobileMenuToggle }: TopBarProps) {
  const { user, logout } = useAuth();
  const { mode, toggleMode } = useThemeMode();
  const navigate = useNavigate();

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const menuOpen = Boolean(anchorEl);

  const [notifAnchorEl, setNotifAnchorEl] = useState<null | HTMLElement>(null);
  const notifOpen = Boolean(notifAnchorEl);

  const { data: unreadData } = useUnreadCount();
  const unreadCount = unreadData?.count ?? 0;
  const { data: notifData } = useNotifications({ pageSize: 5, unreadOnly: false });
  const recentNotifications = notifData?.notifications?.items ?? [];
  const markRead = useMarkRead();

  function getNotificationRoute(notif: NotificationDto): string | null {
    const { entityType, entityId } = notif;
    if (!entityType || !entityId) return null;
    switch (entityType.toLowerCase()) {
      case 'opportunity': return `/opportunities/${entityId}`;
      case 'award': return `/awards/${entityId}`;
      case 'entity': return `/entities/${entityId}`;
      case 'prospect': return `/prospects/${entityId}`;
      case 'saved_search': return '/saved-searches';
      default: return null;
    }
  }

  function handleNotificationClick(notif: NotificationDto) {
    if (!notif.isRead) {
      markRead.mutate(notif.notificationId);
    }
    setNotifAnchorEl(null);
    const route = getNotificationRoute(notif);
    if (route) {
      navigate(route);
    }
  }

  const sidebarWidth = sidebarCollapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED;

  function handleMenuOpen(event: React.MouseEvent<HTMLElement>) {
    setAnchorEl(event.currentTarget);
  }

  function handleMenuClose() {
    setAnchorEl(null);
  }

  function handleNavigate(path: string) {
    handleMenuClose();
    navigate(path);
  }

  async function handleLogout() {
    handleMenuClose();
    await logout();
    navigate('/login');
  }

  const initials = user
    ? user.displayName
        .split(' ')
        .map((n) => n.charAt(0))
        .slice(0, 2)
        .join('')
        .toUpperCase() || user.username.charAt(0).toUpperCase()
    : '?';

  return (
    <AppBar
      position="fixed"
      elevation={0}
      sx={{
        width: { md: `calc(100% - ${sidebarWidth}px)` },
        ml: { md: `${sidebarWidth}px` },
        transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1), margin-left 225ms cubic-bezier(0.4, 0, 0.6, 1)',
        '@media (prefers-reduced-motion: reduce)': {
          transition: 'none',
        },
        bgcolor: 'background.paper',
        color: 'text.primary',
        borderBottom: 1,
        borderColor: 'divider',
      }}
    >
      <Toolbar sx={{ gap: 1 }}>
        {/* Mobile menu toggle */}
        <IconButton
          edge="start"
          onClick={onMobileMenuToggle}
          sx={{ display: { md: 'none' } }}
          aria-label="Open navigation"
        >
          <MenuIcon />
        </IconButton>

        {/* Breadcrumbs */}
        <Breadcrumb />

        {/* Right-side actions */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {/* Theme toggle */}
          <IconButton onClick={toggleMode} size="small" aria-label={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
            {mode === 'dark' ? <Brightness7 /> : <Brightness4 />}
          </IconButton>

          {/* Notifications */}
          <IconButton
            size="small"
            aria-label={unreadCount > 0 ? `View notifications (${unreadCount} unread)` : 'View notifications'}
            onClick={(e) => setNotifAnchorEl(e.currentTarget)}
          >
            <Badge badgeContent={unreadCount} color="error">
              <NotificationsOutlined />
            </Badge>
          </IconButton>
          <Popover
            open={notifOpen}
            anchorEl={notifAnchorEl}
            onClose={() => setNotifAnchorEl(null)}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            slotProps={{ paper: { sx: { mt: 1 } } }}
          >
            <Box sx={{ width: 360, maxHeight: 400 }}>
              <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle1" fontWeight={600}>Notifications</Typography>
                {unreadCount > 0 && <Chip label={`${unreadCount} unread`} size="small" color="primary" />}
              </Box>
              <Divider />
              {recentNotifications.length === 0 ? (
                <Box sx={{ p: 3, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">No notifications</Typography>
                </Box>
              ) : (
                <List disablePadding>
                  {recentNotifications.map((notif) => (
                    <ListItem key={notif.notificationId} disablePadding>
                      <ListItemButton
                        onClick={() => handleNotificationClick(notif)}
                        sx={{ bgcolor: notif.isRead ? 'transparent' : 'action.hover' }}
                      >
                        <ListItemText
                          primary={notif.title}
                          secondary={formatRelative(notif.createdAt)}
                          primaryTypographyProps={{ noWrap: true, fontSize: '0.875rem' }}
                          secondaryTypographyProps={{ fontSize: '0.75rem' }}
                        />
                      </ListItemButton>
                    </ListItem>
                  ))}
                </List>
              )}
              <Divider />
              <Box sx={{ p: 1, textAlign: 'center' }}>
                <Button size="small" onClick={() => { setNotifAnchorEl(null); navigate('/notifications'); }}>
                  View all notifications
                </Button>
              </Box>
            </Box>
          </Popover>

          {/* User menu */}
          <IconButton
            onClick={handleMenuOpen}
            size="small"
            aria-label="Account menu"
            aria-controls={menuOpen ? 'account-menu' : undefined}
            aria-haspopup="true"
            aria-expanded={menuOpen ? 'true' : undefined}
          >
            <Avatar
              sx={{
                width: 32,
                height: 32,
                fontSize: '0.875rem',
                bgcolor: 'primary.main',
              }}
            >
              {initials}
            </Avatar>
          </IconButton>
        </Box>

        {/* User dropdown menu */}
        <Menu
          id="account-menu"
          anchorEl={anchorEl}
          open={menuOpen}
          onClose={handleMenuClose}
          onClick={handleMenuClose}
          transformOrigin={{ horizontal: 'right', vertical: 'top' }}
          anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          slotProps={{
            paper: {
              sx: { width: 220, mt: 1 },
            },
          }}
        >
          {user && (
            <Box sx={{ px: 2, py: 1.5 }}>
              <Typography variant="subtitle2" noWrap>
                {user.displayName}
              </Typography>
              <Typography variant="body2" color="text.secondary" noWrap>
                {user.email ?? user.username}
              </Typography>
            </Box>
          )}
          <Divider />
          <MenuItem onClick={() => handleNavigate('/profile')}>
            <ListItemIcon>
              <PersonOutlined fontSize="small" />
            </ListItemIcon>
            Profile
          </MenuItem>
          <MenuItem onClick={() => handleNavigate('/organization')}>
            <ListItemIcon>
              <CorporateFareOutlined fontSize="small" />
            </ListItemIcon>
            Organization
          </MenuItem>
          <Divider />
          <MenuItem onClick={handleLogout}>
            <ListItemIcon>
              <LogoutOutlined fontSize="small" />
            </ListItemIcon>
            Sign Out
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  );
}
