import { useLocation, useNavigate } from 'react-router-dom';
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
import DashboardOutlined from '@mui/icons-material/DashboardOutlined';
import SearchOutlined from '@mui/icons-material/SearchOutlined';
import EmojiEventsOutlined from '@mui/icons-material/EmojiEventsOutlined';
import BusinessOutlined from '@mui/icons-material/BusinessOutlined';
import GroupsOutlined from '@mui/icons-material/GroupsOutlined';
import TrackChangesOutlined from '@mui/icons-material/TrackChangesOutlined';
import BookmarkBorderOutlined from '@mui/icons-material/BookmarkBorderOutlined';
import CorporateFareOutlined from '@mui/icons-material/CorporateFareOutlined';
import AdminPanelSettingsOutlined from '@mui/icons-material/AdminPanelSettingsOutlined';
import AccountTreeOutlined from '@mui/icons-material/AccountTreeOutlined';
import EventBusyOutlined from '@mui/icons-material/EventBusyOutlined';
import RecommendOutlined from '@mui/icons-material/RecommendOutlined';
import ShowChartOutlined from '@mui/icons-material/ShowChartOutlined';
import GavelOutlined from '@mui/icons-material/GavelOutlined';
import CalculateOutlined from '@mui/icons-material/CalculateOutlined';
import TrendingUpOutlined from '@mui/icons-material/TrendingUpOutlined';
import AssessmentOutlined from '@mui/icons-material/AssessmentOutlined';
import HandshakeOutlined from '@mui/icons-material/HandshakeOutlined';
import MapOutlined from '@mui/icons-material/MapOutlined';
import AutorenewOutlined from '@mui/icons-material/AutorenewOutlined';
import InsightsOutlined from '@mui/icons-material/InsightsOutlined';
import ApartmentOutlined from '@mui/icons-material/ApartmentOutlined';
import PersonSearchOutlined from '@mui/icons-material/PersonSearchOutlined';
import SupervisorAccountOutlined from '@mui/icons-material/SupervisorAccountOutlined';
import CompareOutlined from '@mui/icons-material/CompareOutlined';
import VerifiedUserOutlined from '@mui/icons-material/VerifiedUserOutlined';
import StraightenOutlined from '@mui/icons-material/StraightenOutlined';
import WorkHistoryOutlined from '@mui/icons-material/WorkHistoryOutlined';
import DonutSmallOutlined from '@mui/icons-material/DonutSmallOutlined';
import HealthAndSafetyOutlined from '@mui/icons-material/HealthAndSafetyOutlined';
import AnalyticsOutlined from '@mui/icons-material/AnalyticsOutlined';
import CalendarMonthOutlined from '@mui/icons-material/CalendarMonthOutlined';
import ReportProblemOutlined from '@mui/icons-material/ReportProblemOutlined';
import MonetizationOnOutlined from '@mui/icons-material/MonetizationOnOutlined';
import AccountCircleOutlined from '@mui/icons-material/AccountCircleOutlined';
import ChevronLeft from '@mui/icons-material/ChevronLeft';
import ChevronRight from '@mui/icons-material/ChevronRight';
import { useAuth } from '@/auth/useAuth';

export const SIDEBAR_WIDTH_EXPANDED = 240;
export const SIDEBAR_WIDTH_COLLAPSED = 64;

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

interface NavItem {
  label: string;
  icon: React.ReactElement;
  route: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: 'Main',
    items: [
      { label: 'Dashboard', icon: <DashboardOutlined />, route: '/dashboard' },
    ],
  },
  {
    title: 'Pipeline',
    items: [
      { label: 'Recommended', icon: <RecommendOutlined />, route: '/opportunities/recommended' },
      { label: 'Expiring Contracts', icon: <EventBusyOutlined />, route: '/awards/expiring' },
      { label: 'Prospects', icon: <TrackChangesOutlined />, route: '/prospects' },
      { label: 'Analytics', icon: <AnalyticsOutlined />, route: '/pipeline/analytics' },
      { label: 'Calendar', icon: <CalendarMonthOutlined />, route: '/pipeline/calendar' },
      { label: 'Stale Alerts', icon: <ReportProblemOutlined />, route: '/pipeline/stale' },
      { label: 'Forecast', icon: <MonetizationOnOutlined />, route: '/pipeline/forecast' },
    ],
  },
  {
    title: 'Research',
    items: [
      { label: 'Opportunities', icon: <SearchOutlined />, route: '/opportunities' },
      { label: 'Awards', icon: <EmojiEventsOutlined />, route: '/awards' },
      { label: 'Entities', icon: <BusinessOutlined />, route: '/entities' },
      { label: 'Teaming', icon: <GroupsOutlined />, route: '/subawards/teaming' },
      { label: 'Federal Hierarchy', icon: <AccountTreeOutlined />, route: '/hierarchy' },
    ],
  },
  {
    title: 'Pricing Intelligence',
    items: [
      { label: 'Market Rates', icon: <ShowChartOutlined />, route: '/pricing/rates' },
      { label: 'Price-to-Win', icon: <GavelOutlined />, route: '/pricing/price-to-win' },
      { label: 'Bid Scenarios', icon: <CalculateOutlined />, route: '/pricing/scenarios' },
      { label: 'Escalation', icon: <TrendingUpOutlined />, route: '/pricing/escalation' },
      { label: 'IGCE Estimator', icon: <AssessmentOutlined />, route: '/pricing/igce' },
      { label: 'Sub Benchmarks', icon: <HandshakeOutlined />, route: '/pricing/sub-benchmarks' },
      { label: 'SCA Area Rates', icon: <MapOutlined />, route: '/pricing/sca-rates' },
    ],
  },
  {
    title: 'Competitive Intel',
    items: [
      { label: 'Re-compete Candidates', icon: <AutorenewOutlined />, route: '/competitive-intel/recompetes' },
      { label: 'Agency Patterns', icon: <InsightsOutlined />, route: '/competitive-intel/agency-patterns' },
      { label: 'Contracting Offices', icon: <ApartmentOutlined />, route: '/competitive-intel/offices' },
    ],
  },
  {
    title: 'Teaming',
    items: [
      { label: 'Partner Search', icon: <PersonSearchOutlined />, route: '/teaming/partners' },
      { label: 'Mentor-Protege', icon: <SupervisorAccountOutlined />, route: '/teaming/mentor-protege' },
      { label: 'Gap Analysis', icon: <CompareOutlined />, route: '/teaming/gap-analysis' },
    ],
  },
  {
    title: 'Onboarding',
    items: [
      { label: 'Certification Alerts', icon: <VerifiedUserOutlined />, route: '/onboarding/certification-alerts' },
      { label: 'Size Standard', icon: <StraightenOutlined />, route: '/onboarding/size-standard' },
      { label: 'Past Performance', icon: <WorkHistoryOutlined />, route: '/onboarding/past-performance' },
      { label: 'Portfolio Gaps', icon: <DonutSmallOutlined />, route: '/onboarding/portfolio-gaps' },
    ],
  },
  {
    title: 'Tools',
    items: [
      { label: 'Saved Searches', icon: <BookmarkBorderOutlined />, route: '/saved-searches' },
      { label: 'Data Quality', icon: <HealthAndSafetyOutlined />, route: '/insights/data-quality' },
    ],
  },
  {
    title: 'Settings',
    items: [
      { label: 'Profile', icon: <AccountCircleOutlined />, route: '/profile' },
      { label: 'Organization', icon: <CorporateFareOutlined />, route: '/organization' },
    ],
  },
];

const ADMIN_ITEM: NavItem = {
  label: 'Admin',
  icon: <AdminPanelSettingsOutlined />,
  route: '/admin',
};

export function Sidebar({ collapsed, onToggle, mobileOpen, onMobileClose }: SidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { isSystemAdmin } = useAuth();

  const sidebarWidth = collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED;

  function isActive(route: string): boolean {
    return location.pathname === route || location.pathname.startsWith(route + '/');
  }

  function handleNav(route: string) {
    navigate(route);
    onMobileClose();
  }

  function renderNavItem(item: NavItem) {
    const active = isActive(item.route);

    const button = (
      <ListItem key={item.route} disablePadding sx={{ display: 'block' }}>
        <ListItemButton
          onClick={() => handleNav(item.route)}
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
              primaryTypographyProps={{
                fontSize: '0.875rem',
                fontWeight: active ? 600 : 400,
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

  const sections = NAV_SECTIONS.map((section) => ({ ...section, items: [...section.items] }));
  if (isSystemAdmin) {
    const settingsSection = sections.find((s) => s.title === 'Settings');
    if (settingsSection) {
      settingsSection.items.push(ADMIN_ITEM);
    }
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
        {sections.map((section, sIndex) => (
          <Box key={section.title}>
            {sIndex > 0 && <Divider sx={{ my: 1, mx: 2 }} />}
            {!collapsed && (
              <Typography
                variant="overline"
                sx={{
                  px: 3,
                  pt: 1,
                  pb: 0.5,
                  display: 'block',
                  color: 'text.secondary',
                  fontSize: '0.68rem',
                  letterSpacing: '0.08em',
                }}
              >
                {section.title}
              </Typography>
            )}
            <List disablePadding>
              {section.items.map(renderNavItem)}
            </List>
          </Box>
        ))}
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
