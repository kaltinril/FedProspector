import { Link as RouterLink, useLocation } from 'react-router-dom';
import Box from '@mui/material/Box';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ChevronLeft from '@mui/icons-material/ChevronLeft';
import ChevronRight from '@mui/icons-material/ChevronRight';
import { DESTINATIONS, HUB_NAV_ITEMS, type NavItem } from '@/components/layout/navConfig';

export const SIDEBAR_WIDTH_EXPANDED = 240;
export const SIDEBAR_WIDTH_COLLAPSED = 64;

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

// All navigable rail routes; used to resolve which single item is active so
// that prefix overlaps (e.g. /opportunities vs /opportunities/recommended)
// highlight only the most specific match.
const ALL_NAV_ROUTES = [...DESTINATIONS, ...HUB_NAV_ITEMS].map((i) => i.route);

function routeMatches(pathname: string, route: string): boolean {
  return pathname === route || pathname.startsWith(route + '/');
}

/**
 * Returns the longest nav route that matches the current pathname, or null.
 * "Longest match wins" so /opportunities/recommended activates Recommended, not
 * Opportunities, even though both prefixes match. Hub routes match by prefix so
 * /pipeline?tab=board still highlights Pipeline.
 */
function resolveActiveRoute(pathname: string): string | null {
  let best: string | null = null;
  for (const route of ALL_NAV_ROUTES) {
    if (routeMatches(pathname, route) && (best === null || route.length > best.length)) {
      best = route;
    }
  }
  return best;
}

export function Sidebar({ collapsed, onToggle, mobileOpen, onMobileClose }: SidebarProps) {
  const location = useLocation();
  const sidebarWidth = collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED;
  const activeRoute = resolveActiveRoute(location.pathname);

  function renderNavItem(item: NavItem, opts: { hub?: boolean } = {}) {
    const active = item.route === activeRoute;

    const button = (
      <ListItem key={item.route} disablePadding sx={{ display: 'block' }}>
        <ListItemButton
          component={RouterLink}
          to={item.route}
          onClick={onMobileClose}
          selected={active}
          aria-current={active ? 'page' : undefined}
          sx={{
            minHeight: 44,
            justifyContent: collapsed ? 'center' : 'initial',
            px: 2.5,
            borderRadius: 1,
            mx: 1,
            mb: 0.25,
          }}
        >
          <ListItemIcon
            sx={{
              minWidth: 0,
              mr: collapsed ? 0 : 2,
              justifyContent: 'center',
              color: active ? 'primary.main' : 'inherit',
            }}
          >
            {item.icon}
          </ListItemIcon>
          {!collapsed && (
            <>
              <ListItemText
                primary={item.label}
                slotProps={{
                  primary: {
                    sx: { fontSize: '0.875rem', fontWeight: active ? 600 : 400 },
                  },
                }}
              />
              {opts.hub && (
                <ChevronRight
                  sx={{
                    fontSize: 18,
                    color: active ? 'inherit' : 'text.disabled',
                    flexShrink: 0,
                  }}
                />
              )}
            </>
          )}
        </ListItemButton>
      </ListItem>
    );

    if (collapsed) {
      return (
        <Tooltip key={item.route} title={item.label} placement="right" arrow>
          {button}
        </Tooltip>
      );
    }

    return button;
  }

  const drawerContent = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Logo / Brand Area */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'flex-start',
          px: collapsed ? 1 : 2,
          py: 1.5,
          minHeight: 64,
        }}
      >
        {!collapsed && (
          <Typography variant="h6" noWrap sx={{ fontWeight: 700, color: 'primary.main' }}>
            FedProspect
          </Typography>
        )}
        {collapsed && (
          <Typography variant="h6" sx={{ fontWeight: 700, color: 'primary.main' }}>
            FP
          </Typography>
        )}
      </Box>

      <Divider />

      {/* Navigation */}
      <Box sx={{ flexGrow: 1, overflowY: 'auto', overflowX: 'hidden', pt: 1 }}>
        {/* Tier 1 — Destinations (flat, no section header) */}
        <List disablePadding>
          {DESTINATIONS.map((item) => renderNavItem(item))}
        </List>

        {/* Tier 2 — Hubs */}
        <Divider sx={{ my: 1, mx: 2 }} />
        {!collapsed && (
          <Typography
            variant="overline"
            sx={{
              display: 'block',
              px: 3,
              pt: 0.5,
              pb: 0.5,
              color: 'text.secondary',
              fontSize: '0.68rem',
              letterSpacing: '0.08em',
              lineHeight: 1.8,
            }}
          >
            Hubs
          </Typography>
        )}
        <List disablePadding>
          {HUB_NAV_ITEMS.map((item) => renderNavItem(item, { hub: true }))}
        </List>
      </Box>

      {/* Collapse Toggle */}
      <Divider />
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
        <IconButton onClick={onToggle} size="small" aria-label="Toggle sidebar">
          {collapsed ? <ChevronRight /> : <ChevronLeft />}
        </IconButton>
      </Box>
    </Box>
  );

  return (
    <Box component="nav">
      {/* Mobile drawer (temporary) */}
      <Drawer
        variant="temporary"
        open={mobileOpen}
        onClose={onMobileClose}
        ModalProps={{ keepMounted: true }}
        sx={{
          display: { xs: 'block', md: 'none' },
          '& .MuiDrawer-paper': {
            width: SIDEBAR_WIDTH_EXPANDED,
            boxSizing: 'border-box',
          },
        }}
      >
        {drawerContent}
      </Drawer>

      {/* Desktop drawer (permanent) */}
      <Drawer
        variant="permanent"
        sx={{
          display: { xs: 'none', md: 'block' },
          '& .MuiDrawer-paper': {
            width: sidebarWidth,
            boxSizing: 'border-box',
            transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1)',
            '@media (prefers-reduced-motion: reduce)': {
              transition: 'none',
            },
            overflowX: 'hidden',
            borderRight: 1,
            borderColor: 'divider',
          },
        }}
        open
      >
        {drawerContent}
      </Drawer>
    </Box>
  );
}
