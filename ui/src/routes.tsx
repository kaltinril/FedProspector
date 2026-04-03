import { lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AdminGuard } from '@/auth/AdminGuard';
import { AuthGuard } from '@/auth/AuthGuard';
import { useAuth } from '@/auth/useAuth';
import { AppLayout } from '@/components/layout/AppLayout';
import { ErrorBoundary } from '@/components/shared/ErrorBoundary';

const LoginPage = lazy(() => import('@/pages/login/LoginPage'));
const RegisterPage = lazy(() => import('@/pages/login/RegisterPage'));
const ChangePasswordPage = lazy(() => import('@/pages/change-password/ChangePasswordPage'));
const DashboardPage = lazy(() => import('@/pages/dashboard/DashboardPage'));
const SetupPage = lazy(() => import('@/pages/setup/SetupPage'));
const OpportunitySearchPage = lazy(
  () => import('@/pages/opportunities/OpportunitySearchPage'),
);
const TargetOpportunityPage = lazy(
  () => import('@/pages/opportunities/TargetOpportunityPage'),
);
const RecommendedOpportunitiesPage = lazy(
  () => import('@/pages/recommendations/RecommendedOpportunitiesPage'),
);
const AwardSearchPage = lazy(() => import('@/pages/awards/AwardSearchPage'));
const ExpiringContractsPage = lazy(() => import('@/pages/awards/ExpiringContractsPage'));
const EntitySearchPage = lazy(() => import('@/pages/entities/EntitySearchPage'));
const OpportunityDetailPage = lazy(
  () => import('@/pages/opportunities/OpportunityDetailPage'),
);
const AwardDetailPage = lazy(() => import('@/pages/awards/AwardDetailPage'));
const EntityDetailPage = lazy(() => import('@/pages/entities/EntityDetailPage'));
const TeamingPartnerPage = lazy(() => import('@/pages/subawards/TeamingPartnerPage'));
const HierarchyBrowsePage = lazy(() => import('@/pages/hierarchy/HierarchyBrowsePage'));
const OrganizationDetailPage = lazy(
  () => import('@/pages/hierarchy/OrganizationDetailPage'),
);
const ProspectPipelinePage = lazy(() => import('@/pages/prospects/ProspectPipelinePage'));
const ProspectDetailPage = lazy(() => import('@/pages/prospects/ProspectDetailPage'));
const ProposalDetailPage = lazy(() => import('@/pages/prospects/ProposalDetailPage'));
const SavedSearchesPage = lazy(() => import('@/pages/saved-searches/SavedSearchesPage'));
const NotificationCenterPage = lazy(
  () => import('@/pages/notifications/NotificationCenterPage'),
);
const AdminPage = lazy(() => import('@/pages/admin/AdminPage'));
const ProfilePage = lazy(() => import('@/pages/profile/ProfilePage'));
const OrganizationPage = lazy(() => import('@/pages/organization/OrganizationPage'));
const RateHeatmapPage = lazy(() => import('@/pages/pricing/RateHeatmapPage'));
const PriceToWinPage = lazy(() => import('@/pages/pricing/PriceToWinPage'));
const BidScenarioPage = lazy(() => import('@/pages/pricing/BidScenarioPage'));
const EscalationPage = lazy(() => import('@/pages/pricing/EscalationPage'));
const IgcePage = lazy(() => import('@/pages/pricing/IgcePage'));
const SubBenchmarkPage = lazy(() => import('@/pages/pricing/SubBenchmarkPage'));
const RecompeteCandidatesPage = lazy(() => import('@/pages/competitive-intel/RecompeteCandidatesPage'));
const AgencyPatternsPage = lazy(() => import('@/pages/competitive-intel/AgencyPatternsPage'));
const CompetitorDossierPage = lazy(() => import('@/pages/competitive-intel/CompetitorDossierPage'));
const ContractingOfficesPage = lazy(() => import('@/pages/competitive-intel/ContractingOfficesPage'));
const OfficeDetailPage = lazy(() => import('@/pages/competitive-intel/OfficeDetailPage'));
const PartnerSearchPage = lazy(() => import('@/pages/teaming/PartnerSearchPage'));
const PartnerDetailPage = lazy(() => import('@/pages/teaming/PartnerDetailPage'));
const MentorProtegePage = lazy(() => import('@/pages/teaming/MentorProtegePage'));
const GapAnalysisPage = lazy(() => import('@/pages/teaming/GapAnalysisPage'));
const PipelineAnalyticsPage = lazy(() => import('@/pages/pipeline/PipelineAnalyticsPage'));
const PipelineCalendarPage = lazy(() => import('@/pages/pipeline/PipelineCalendarPage'));
const StaleProspectsPage = lazy(() => import('@/pages/pipeline/StaleProspectsPage'));
const RevenueForecastPage = lazy(() => import('@/pages/pipeline/RevenueForecastPage'));
const CertificationAlertsPage = lazy(() => import('@/pages/onboarding/CertificationAlertsPage'));
const SizeStandardMonitorPage = lazy(() => import('@/pages/onboarding/SizeStandardMonitorPage'));
const PastPerformanceRelevancePage = lazy(() => import('@/pages/onboarding/PastPerformanceRelevancePage'));
const PortfolioGapAnalysisPage = lazy(() => import('@/pages/onboarding/PortfolioGapAnalysisPage'));
const DataQualityDashboardPage = lazy(() => import('@/pages/insights/DataQualityDashboardPage'));
const NotFoundPage = lazy(() => import('@/pages/errors/NotFoundPage'));

function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppLayout>
        <ErrorBoundary>{children}</ErrorBoundary>
      </AppLayout>
    </AuthGuard>
  );
}

/**
 * Shows 404 within AppLayout if authenticated, or standalone if not.
 * This ensures unauthenticated users see a proper 404 instead of being
 * redirected to login.
 */
function NotFoundLayout() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <NotFoundPage />;
  }

  if (isAuthenticated) {
    return (
      <AppLayout>
        <ErrorBoundary>
          <NotFoundPage />
        </ErrorBoundary>
      </AppLayout>
    );
  }

  return <NotFoundPage />;
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Root redirect */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/change-password" element={<ChangePasswordPage />} />

      {/* Authenticated routes with layout */}
      <Route
        path="/setup"
        element={
          <AuthenticatedLayout>
            <SetupPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/dashboard"
        element={
          <AuthenticatedLayout>
            <DashboardPage />
          </AuthenticatedLayout>
        }
      />

      {/* Search routes */}
      <Route
        path="/opportunities"
        element={
          <AuthenticatedLayout>
            <OpportunitySearchPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/opportunities/recommended"
        element={
          <AuthenticatedLayout>
            <RecommendedOpportunitiesPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/opportunities/:noticeId"
        element={
          <AuthenticatedLayout>
            <OpportunityDetailPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/opportunities/targets"
        element={
          <AuthenticatedLayout>
            <TargetOpportunityPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/awards"
        element={
          <AuthenticatedLayout>
            <AwardSearchPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/awards/expiring"
        element={
          <AuthenticatedLayout>
            <ExpiringContractsPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/awards/:contractId"
        element={
          <AuthenticatedLayout>
            <AwardDetailPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/entities"
        element={
          <AuthenticatedLayout>
            <EntitySearchPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/entities/:uei"
        element={
          <AuthenticatedLayout>
            <EntityDetailPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/subawards/teaming"
        element={
          <AuthenticatedLayout>
            <TeamingPartnerPage />
          </AuthenticatedLayout>
        }
      />

      {/* Federal Hierarchy */}
      <Route
        path="/hierarchy"
        element={
          <AuthenticatedLayout>
            <HierarchyBrowsePage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/hierarchy/:fhOrgId"
        element={
          <AuthenticatedLayout>
            <OrganizationDetailPage />
          </AuthenticatedLayout>
        }
      />

      {/* Prospect pipeline */}
      <Route
        path="/prospects"
        element={
          <AuthenticatedLayout>
            <ProspectPipelinePage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/prospects/:id"
        element={
          <AuthenticatedLayout>
            <ProspectDetailPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/prospects/:id/proposals/:proposalId"
        element={
          <AuthenticatedLayout>
            <ProposalDetailPage />
          </AuthenticatedLayout>
        }
      />

      {/* Pipeline Analytics */}
      <Route
        path="/pipeline/analytics"
        element={
          <AuthenticatedLayout>
            <PipelineAnalyticsPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/pipeline/calendar"
        element={
          <AuthenticatedLayout>
            <PipelineCalendarPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/pipeline/stale"
        element={
          <AuthenticatedLayout>
            <StaleProspectsPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/pipeline/forecast"
        element={
          <AuthenticatedLayout>
            <RevenueForecastPage />
          </AuthenticatedLayout>
        }
      />

      {/* Pricing Intelligence */}
      <Route
        path="/pricing/rates"
        element={
          <AuthenticatedLayout>
            <RateHeatmapPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/pricing/price-to-win"
        element={
          <AuthenticatedLayout>
            <PriceToWinPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/pricing/scenarios"
        element={
          <AuthenticatedLayout>
            <BidScenarioPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/pricing/escalation"
        element={
          <AuthenticatedLayout>
            <EscalationPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/pricing/igce"
        element={
          <AuthenticatedLayout>
            <IgcePage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/pricing/sub-benchmarks"
        element={
          <AuthenticatedLayout>
            <SubBenchmarkPage />
          </AuthenticatedLayout>
        }
      />

      {/* Competitive Intelligence */}
      <Route
        path="/competitive-intel/recompetes"
        element={
          <AuthenticatedLayout>
            <RecompeteCandidatesPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/competitive-intel/agency-patterns"
        element={
          <AuthenticatedLayout>
            <AgencyPatternsPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/competitive-intel/competitor/:uei"
        element={
          <AuthenticatedLayout>
            <CompetitorDossierPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/competitive-intel/offices"
        element={
          <AuthenticatedLayout>
            <ContractingOfficesPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/competitive-intel/offices/:officeCode"
        element={
          <AuthenticatedLayout>
            <OfficeDetailPage />
          </AuthenticatedLayout>
        }
      />

      {/* Teaming & Partnership Intelligence */}
      <Route
        path="/teaming/partners"
        element={
          <AuthenticatedLayout>
            <PartnerSearchPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/teaming/partner/:uei"
        element={
          <AuthenticatedLayout>
            <PartnerDetailPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/teaming/mentor-protege"
        element={
          <AuthenticatedLayout>
            <MentorProtegePage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/teaming/gap-analysis"
        element={
          <AuthenticatedLayout>
            <GapAnalysisPage />
          </AuthenticatedLayout>
        }
      />

      {/* Onboarding & Past Performance */}
      <Route
        path="/onboarding/certification-alerts"
        element={
          <AuthenticatedLayout>
            <CertificationAlertsPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/onboarding/size-standard"
        element={
          <AuthenticatedLayout>
            <SizeStandardMonitorPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/onboarding/past-performance"
        element={
          <AuthenticatedLayout>
            <PastPerformanceRelevancePage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/onboarding/portfolio-gaps"
        element={
          <AuthenticatedLayout>
            <PortfolioGapAnalysisPage />
          </AuthenticatedLayout>
        }
      />

      {/* Insights */}
      <Route
        path="/insights/data-quality"
        element={
          <AuthenticatedLayout>
            <DataQualityDashboardPage />
          </AuthenticatedLayout>
        }
      />

      {/* Saved searches */}
      <Route
        path="/saved-searches"
        element={
          <AuthenticatedLayout>
            <SavedSearchesPage />
          </AuthenticatedLayout>
        }
      />

      {/* Notifications */}
      <Route
        path="/notifications"
        element={
          <AuthenticatedLayout>
            <NotificationCenterPage />
          </AuthenticatedLayout>
        }
      />

      {/* User & Org */}
      <Route
        path="/profile"
        element={
          <AuthenticatedLayout>
            <ProfilePage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/organization"
        element={
          <AuthenticatedLayout>
            <OrganizationPage />
          </AuthenticatedLayout>
        }
      />

      {/* Admin */}
      <Route
        path="/admin"
        element={
          <AuthenticatedLayout>
            <AdminGuard>
              <AdminPage />
            </AdminGuard>
          </AuthenticatedLayout>
        }
      />

      {/* 404 catch-all — public so unauthenticated users see 404, not login */}
      <Route
        path="*"
        element={<NotFoundLayout />}
      />
    </Routes>
  );
}
