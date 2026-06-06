import { lazy } from 'react';

/**
 * Lazy wrappers around the existing page components that hubs reuse as tab
 * content. This module exports ONLY components (every export is a lazy page) so
 * it satisfies react-refresh/only-export-components; the data-only hub config in
 * hubConfig.tsx imports these and never declares components of its own.
 *
 * None of these pages are modified — each hub renders the exact page that lived
 * at its old standalone route. The lazy() boundary keeps every tab in its own
 * JS chunk so opening a hub never loads code for non-active tabs.
 */

// Pipeline
export const ProspectPipelinePage = lazy(() => import('@/pages/prospects/ProspectPipelinePage'));
export const RevenueForecastPage = lazy(() => import('@/pages/pipeline/RevenueForecastPage'));
export const PipelineAnalyticsPage = lazy(() => import('@/pages/pipeline/PipelineAnalyticsPage'));
export const PipelineCalendarPage = lazy(() => import('@/pages/pipeline/PipelineCalendarPage'));
export const StaleProspectsPage = lazy(() => import('@/pages/pipeline/StaleProspectsPage'));
export const ExpiringContractsPage = lazy(() => import('@/pages/awards/ExpiringContractsPage'));

// Pricing
export const RateHeatmapPage = lazy(() => import('@/pages/pricing/RateHeatmapPage'));
export const PriceToWinPage = lazy(() => import('@/pages/pricing/PriceToWinPage'));
export const BidScenarioPage = lazy(() => import('@/pages/pricing/BidScenarioPage'));
export const EscalationPage = lazy(() => import('@/pages/pricing/EscalationPage'));
export const IgcePage = lazy(() => import('@/pages/pricing/IgcePage'));
export const SubBenchmarkPage = lazy(() => import('@/pages/pricing/SubBenchmarkPage'));
export const ScaGeographicPage = lazy(() => import('@/pages/pricing/ScaGeographicPage'));

// Teaming
export const PartnerSearchPage = lazy(() => import('@/pages/teaming/PartnerSearchPage'));
export const MentorProtegePage = lazy(() => import('@/pages/teaming/MentorProtegePage'));
export const GapAnalysisPage = lazy(() => import('@/pages/teaming/GapAnalysisPage'));
export const TeamingPartnerPage = lazy(() => import('@/pages/subawards/TeamingPartnerPage'));

// Market Intel
export const AgencyPatternsPage = lazy(() => import('@/pages/competitive-intel/AgencyPatternsPage'));
export const ContractingOfficesPage = lazy(() => import('@/pages/competitive-intel/ContractingOfficesPage'));
export const RecompeteCandidatesPage = lazy(() => import('@/pages/competitive-intel/RecompeteCandidatesPage'));
export const HierarchyBrowsePage = lazy(() => import('@/pages/hierarchy/HierarchyBrowsePage'));
export const NaicsBrowserPage = lazy(() => import('@/pages/reference/NaicsBrowserPage'));

// Company & Eligibility
export const CertificationAlertsPage = lazy(() => import('@/pages/onboarding/CertificationAlertsPage'));
export const SizeStandardMonitorPage = lazy(() => import('@/pages/onboarding/SizeStandardMonitorPage'));
export const PastPerformanceRelevancePage = lazy(() => import('@/pages/onboarding/PastPerformanceRelevancePage'));
export const PortfolioGapAnalysisPage = lazy(() => import('@/pages/onboarding/PortfolioGapAnalysisPage'));
