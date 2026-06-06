import AccountTreeOutlined from '@mui/icons-material/AccountTreeOutlined';
import AnalyticsOutlined from '@mui/icons-material/AnalyticsOutlined';
import ApartmentOutlined from '@mui/icons-material/ApartmentOutlined';
import AssessmentOutlined from '@mui/icons-material/AssessmentOutlined';
import AutorenewOutlined from '@mui/icons-material/AutorenewOutlined';
import BadgeOutlined from '@mui/icons-material/BadgeOutlined';
import BarChartOutlined from '@mui/icons-material/BarChartOutlined';
import CalculateOutlined from '@mui/icons-material/CalculateOutlined';
import CalendarMonthOutlined from '@mui/icons-material/CalendarMonthOutlined';
import CategoryOutlined from '@mui/icons-material/CategoryOutlined';
import CompareOutlined from '@mui/icons-material/CompareOutlined';
import DonutSmallOutlined from '@mui/icons-material/DonutSmallOutlined';
import EventBusyOutlined from '@mui/icons-material/EventBusyOutlined';
import ExploreOutlined from '@mui/icons-material/ExploreOutlined';
import GavelOutlined from '@mui/icons-material/GavelOutlined';
import HandshakeOutlined from '@mui/icons-material/HandshakeOutlined';
import HubOutlined from '@mui/icons-material/HubOutlined';
import InsightsOutlined from '@mui/icons-material/InsightsOutlined';
import MapOutlined from '@mui/icons-material/MapOutlined';
import MonetizationOnOutlined from '@mui/icons-material/MonetizationOnOutlined';
import PaidOutlined from '@mui/icons-material/PaidOutlined';
import PersonSearchOutlined from '@mui/icons-material/PersonSearchOutlined';
import ReportProblemOutlined from '@mui/icons-material/ReportProblemOutlined';
import ShowChartOutlined from '@mui/icons-material/ShowChartOutlined';
import StraightenOutlined from '@mui/icons-material/StraightenOutlined';
import SupervisorAccountOutlined from '@mui/icons-material/SupervisorAccountOutlined';
import TravelExploreOutlined from '@mui/icons-material/TravelExploreOutlined';
import TrendingUpOutlined from '@mui/icons-material/TrendingUpOutlined';
import VerifiedUserOutlined from '@mui/icons-material/VerifiedUserOutlined';
import ViewKanbanOutlined from '@mui/icons-material/ViewKanbanOutlined';
import WorkHistoryOutlined from '@mui/icons-material/WorkHistoryOutlined';

import {
  AgencyPatternsPage,
  BidScenarioPage,
  CertificationAlertsPage,
  ContractingOfficesPage,
  EscalationPage,
  ExpiringContractsPage,
  GapAnalysisPage,
  HierarchyBrowsePage,
  IgcePage,
  MentorProtegePage,
  NaicsBrowserPage,
  PartnerSearchPage,
  PastPerformanceRelevancePage,
  PipelineAnalyticsPage,
  PipelineCalendarPage,
  PortfolioGapAnalysisPage,
  PriceToWinPage,
  ProspectPipelinePage,
  RateHeatmapPage,
  RecompeteCandidatesPage,
  RevenueForecastPage,
  ScaGeographicPage,
  SizeStandardMonitorPage,
  StaleProspectsPage,
  SubBenchmarkPage,
  TeamingPartnerPage,
} from '@/components/layout/hubPages';

export interface HubTab {
  /** URL slug used in ?tab=<slug>; deep-linkable and stable. */
  slug: string;
  label: string;
  icon: React.ReactElement;
  /** The existing page component reused verbatim as this tab's content. */
  component: React.LazyExoticComponent<React.ComponentType>;
  /** Former standalone route, redirected to `${hub.route}?tab=${slug}`. */
  oldRoute: string;
}

export interface Hub {
  /** Hub id (also used as the section/localStorage key). */
  id: string;
  /** Tier-2 hub landing route, e.g. /pipeline. */
  route: string;
  label: string;
  subtitle: string;
  icon: React.ReactElement;
  tabs: HubTab[];
}

export const HUBS: Hub[] = [
  {
    id: 'pipeline',
    route: '/pipeline',
    label: 'Pipeline',
    subtitle: 'Move opportunities from discovery to decision.',
    icon: <BarChartOutlined />,
    tabs: [
      { slug: 'board', label: 'Board', icon: <ViewKanbanOutlined />, component: ProspectPipelinePage, oldRoute: '/pipeline/board' },
      { slug: 'forecast', label: 'Forecast', icon: <MonetizationOnOutlined />, component: RevenueForecastPage, oldRoute: '/pipeline/forecast' },
      { slug: 'analytics', label: 'Analytics', icon: <AnalyticsOutlined />, component: PipelineAnalyticsPage, oldRoute: '/pipeline/analytics' },
      { slug: 'calendar', label: 'Calendar', icon: <CalendarMonthOutlined />, component: PipelineCalendarPage, oldRoute: '/pipeline/calendar' },
      { slug: 'stale', label: 'Stale Alerts', icon: <ReportProblemOutlined />, component: StaleProspectsPage, oldRoute: '/pipeline/stale' },
      { slug: 'expiring', label: 'Expiring Contracts', icon: <EventBusyOutlined />, component: ExpiringContractsPage, oldRoute: '/awards/expiring' },
    ],
  },
  {
    id: 'pricing',
    route: '/pricing',
    label: 'Pricing',
    subtitle: 'Build and defend your price-to-win.',
    icon: <PaidOutlined />,
    tabs: [
      { slug: 'rates', label: 'Market Rates', icon: <ShowChartOutlined />, component: RateHeatmapPage, oldRoute: '/pricing/rates' },
      { slug: 'price-to-win', label: 'Price-to-Win', icon: <GavelOutlined />, component: PriceToWinPage, oldRoute: '/pricing/price-to-win' },
      { slug: 'scenarios', label: 'Bid Scenarios', icon: <CalculateOutlined />, component: BidScenarioPage, oldRoute: '/pricing/scenarios' },
      { slug: 'escalation', label: 'Escalation', icon: <TrendingUpOutlined />, component: EscalationPage, oldRoute: '/pricing/escalation' },
      { slug: 'igce', label: 'IGCE Estimator', icon: <AssessmentOutlined />, component: IgcePage, oldRoute: '/pricing/igce' },
      { slug: 'sub-benchmarks', label: 'Sub Benchmarks', icon: <HandshakeOutlined />, component: SubBenchmarkPage, oldRoute: '/pricing/sub-benchmarks' },
      { slug: 'sca-rates', label: 'SCA Area Rates', icon: <MapOutlined />, component: ScaGeographicPage, oldRoute: '/pricing/sca-rates' },
    ],
  },
  {
    id: 'teaming',
    route: '/teaming',
    label: 'Teaming',
    subtitle: 'Find partners and fill capability gaps.',
    icon: <HandshakeOutlined />,
    tabs: [
      { slug: 'partners', label: 'Partner Search', icon: <PersonSearchOutlined />, component: PartnerSearchPage, oldRoute: '/teaming/partners' },
      { slug: 'mentor-protege', label: 'Mentor-Protégé', icon: <SupervisorAccountOutlined />, component: MentorProtegePage, oldRoute: '/teaming/mentor-protege' },
      { slug: 'gap-analysis', label: 'Gap Analysis', icon: <CompareOutlined />, component: GapAnalysisPage, oldRoute: '/teaming/gap-analysis' },
      { slug: 'subaward-network', label: 'Subaward Network', icon: <AccountTreeOutlined />, component: TeamingPartnerPage, oldRoute: '/subawards/teaming' },
    ],
  },
  {
    id: 'market-intel',
    route: '/market-intel',
    label: 'Market Intel',
    subtitle: 'Understand agencies, offices and re-compete timing.',
    icon: <TravelExploreOutlined />,
    tabs: [
      { slug: 'agency-patterns', label: 'Agency Patterns', icon: <InsightsOutlined />, component: AgencyPatternsPage, oldRoute: '/competitive-intel/agency-patterns' },
      { slug: 'offices', label: 'Contracting Offices', icon: <ApartmentOutlined />, component: ContractingOfficesPage, oldRoute: '/competitive-intel/offices' },
      { slug: 'recompetes', label: 'Re-compete Candidates', icon: <AutorenewOutlined />, component: RecompeteCandidatesPage, oldRoute: '/competitive-intel/recompetes' },
      { slug: 'hierarchy', label: 'Federal Hierarchy', icon: <ExploreOutlined />, component: HierarchyBrowsePage, oldRoute: '/hierarchy' },
      { slug: 'naics', label: 'NAICS Browser', icon: <CategoryOutlined />, component: NaicsBrowserPage, oldRoute: '/reference/naics' },
    ],
  },
  {
    id: 'company',
    route: '/company',
    label: 'Company & Eligibility',
    subtitle: 'Keep certifications, size and past performance current.',
    icon: <BadgeOutlined />,
    tabs: [
      { slug: 'certification-alerts', label: 'Certification Alerts', icon: <VerifiedUserOutlined />, component: CertificationAlertsPage, oldRoute: '/onboarding/certification-alerts' },
      { slug: 'size-standard', label: 'Size Standard', icon: <StraightenOutlined />, component: SizeStandardMonitorPage, oldRoute: '/onboarding/size-standard' },
      { slug: 'past-performance', label: 'Past Performance', icon: <WorkHistoryOutlined />, component: PastPerformanceRelevancePage, oldRoute: '/onboarding/past-performance' },
      { slug: 'portfolio-gaps', label: 'Portfolio Gaps', icon: <DonutSmallOutlined />, component: PortfolioGapAnalysisPage, oldRoute: '/onboarding/portfolio-gaps' },
    ],
  },
];

/** Generic "hubs" group glyph for the sidebar section header. */
export const HUBS_GROUP_ICON = <HubOutlined />;

export const HUB_BY_ID: Record<string, Hub> = Object.fromEntries(
  HUBS.map((hub) => [hub.id, hub]),
);

/**
 * Flat list of every former leaf route and the hub `?tab=` URL it should
 * redirect to. Used to register backward-compatible redirects in the router so
 * existing bookmarks and in-app links keep working. The `/pipeline/board`
 * pseudo-route has no real predecessor (Board did not exist as its own route
 * before) but is included so the canonical board deep-link resolves cleanly.
 */
export const HUB_REDIRECTS: { from: string; to: string }[] = HUBS.flatMap((hub) =>
  hub.tabs.map((tab) => ({
    from: tab.oldRoute,
    to: `${hub.route}?tab=${tab.slug}`,
  })),
);
