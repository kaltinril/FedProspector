import { useEffect } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import Box from '@mui/material/Box';
import Drawer from '@mui/material/Drawer';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Collapse from '@mui/material/Collapse';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ChevronLeft from '@mui/icons-material/ChevronLeft';
import ChevronRight from '@mui/icons-material/ChevronRight';
import ExpandMore from '@mui/icons-material/ExpandMore';
import { useAuth } from '@/auth/useAuth';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { getNavSections, type NavItem, type NavSection } from '@/components/layout/navConfig';

export const SIDEBAR_WIDTH_EXPANDED = 240;
export const SIDEBAR_WIDTH_COLLAPSED = 64;

const SECTION_STATE_KEY = 'sidebar.sectionExpanded';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

function isRouteActive(pathname: string, route: string): boolean {
  return pathname === route || pathname.startsWith(route + '/');
}

export function Sidebar({ collapsed, onToggle, mobileOpen, onMobileClose }: SidebarProps) {
  const location = useLocation();
  const { isSystemAdmin } = useAuth();

  // Per-user persisted collapse state for each section header, keyed by section
  // title. Sections absent from the map default to expanded.
  const [sectionExpanded, setSectionExpanded] = useLocalStorage<Record<string, boolean>>(
    SECTION_STATE_KEY,
    {},
  );

  const sidebarWidth = collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED;

  const sections = getNavSections(isSystemAdmin);

  // Auto-expand the section that contains the current route so the active item
  // is always visible after navigation / on load.
  useEffect(() => {
    const activeSection = sections.find((section) =>
      section.items.some((item) => isRouteActive(location.pathname, item.route)),
    );
    if (activeSection) {
      setSectionExpanded((prev) =>
        prev[activeSection.title] === false
          ? { ...prev, [activeSection.title]: true }
          : prev,
      );
    }
    // `sections` is derived synchronously from a stable module constant, so the
    // pathname is the only meaningful dependency for recomputing the active section.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  function isSectionExpanded(title: string): boolean {
    return sectionExpanded[title] !== false;
  }

  function toggleSection(title: string) {
    setSectionExpanded((prev) => ({ ...prev, [title]: prev[title] === false }));
  }

  function isActive(route: string): boolean {
    return isRouteActive(location.pathname, route);
  }

  function renderNavItem(item: NavItem) {
    const active = isActive(item.route);

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
            <ListItemText
              primary={item.label}
              slotProps={{
                primary: {
                  sx: { fontSize: '0.875rem', fontWeight: active ? 600 : 400 },
                }
              }}
            />
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

  function renderSection(section: NavSection, sIndex: number) {
    // In icon-rail (collapsed) mode the section headers are hidden, so every
    // group is shown — there is no header to toggle.
    if (collapsed) {
      return (
        <Box key={section.title}>
          {sIndex > 0 && <Divider sx={{ my: 1, mx: 2 }} />}
          <List disablePadding>
            {section.items.map(renderNavItem)}
          </List>
        </Box>
      );
    }

    const expanded = isSectionExpanded(section.title);

    return (
      <Box key={section.title}>
        {sIndex > 0 && <Divider sx={{ my: 1, mx: 2 }} />}
        <ListItemButton
          onClick={() => toggleSection(section.title)}
          aria-expanded={expanded}
          sx={{
            px: 3,
            pt: 1,
            pb: 0.5,
            minHeight: 0,
            '&:hover': { bgcolor: 'action.hover' },
          }}
        >
          <Typography
            variant="overline"
            sx={{
              flexGrow: 1,
              display: 'block',
              color: 'text.secondary',
              fontSize: '0.68rem',
              letterSpacing: '0.08em',
              lineHeight: 1.8,
            }}
          >
            {section.title}
          </Typography>
          {expanded ? (
            <ExpandMore sx={{ fontSize: 18, color: 'text.secondary' }} />
          ) : (
            <ChevronRight sx={{ fontSize: 18, color: 'text.secondary' }} />
          )}
        </ListItemButton>
        <Collapse in={expanded} timeout="auto" unmountOnExit>
          <List disablePadding>
            {section.items.map(renderNavItem)}
          </List>
        </Collapse>
      </Box>
    );
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
        {sections.map(renderSection)}
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
