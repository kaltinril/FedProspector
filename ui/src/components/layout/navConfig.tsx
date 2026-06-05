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
import CategoryOutlined from '@mui/icons-material/CategoryOutlined';
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

export interface NavItem {
  label: string;
  icon: React.ReactElement;
  route: string;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
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
      { label: 'NAICS Browser', icon: <CategoryOutlined />, route: '/reference/naics' },
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

export const ADMIN_ITEM: NavItem = {
  label: 'Admin',
  icon: <AdminPanelSettingsOutlined />,
  route: '/admin',
};

/**
 * Returns the nav sections, appending the Admin item to the Settings section
 * when the current user is a system admin. Sections and their item arrays are
 * shallow-cloned so callers never mutate the shared NAV_SECTIONS constant.
 */
export function getNavSections(isSystemAdmin: boolean): NavSection[] {
  const sections = NAV_SECTIONS.map((section) => ({ ...section, items: [...section.items] }));
  if (isSystemAdmin) {
    const settingsSection = sections.find((s) => s.title === 'Settings');
    if (settingsSection) {
      settingsSection.items.push(ADMIN_ITEM);
    }
  }
  return sections;
}
