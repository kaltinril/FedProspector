import { lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AdminGuard } from '@/auth/AdminGuard';
import { AuthGuard } from '@/auth/AuthGuard';
import { useAuth } from '@/auth/useAuth';
import { AppLayout } from '@/components/layout/AppLayout';
import { ErrorBoundary } from '@/components/shared/ErrorBoundary';
import { HubPage } from '@/pages/hubs/HubPage';
import { HUBS, HUB_REDIRECTS } from '@/components/layout/hubConfig';

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
const EntitySearchPage = lazy(() => import('@/pages/entities/EntitySearchPage'));
const OpportunityDetailPage = lazy(
  () => import('@/pages/opportunities/OpportunityDetailPage'),
);
const AwardDetailPage = lazy(() => import('@/pages/awards/AwardDetailPage'));
const EntityDetailPage = lazy(() => import('@/pages/entities/EntityDetailPage'));
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
const CompetitorDossierPage = lazy(() => import('@/pages/competitive-intel/CompetitorDossierPage'));
const OfficeDetailPage = lazy(() => import('@/pages/competitive-intel/OfficeDetailPage'));
const PartnerDetailPage = lazy(() => import('@/pages/teaming/PartnerDetailPage'));
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

      {/* ============================================================ */}
      {/* Tier 1 — Destinations (flat pages, routes unchanged)         */}
      {/* ============================================================ */}
      <Route
        path="/dashboard"
        element={
          <AuthenticatedLayout>
            <DashboardPage />
          </AuthenticatedLayout>
        }
      />
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
        path="/opportunities/targets"
        element={
          <AuthenticatedLayout>
            <TargetOpportunityPage />
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
        path="/awards"
        element={
          <AuthenticatedLayout>
            <AwardSearchPage />
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

      {/* Prospects destination + detail routes (Prospects stays Tier-1;
          the Pipeline hub also exposes a Board tab — different views) */}
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

      {/* ============================================================ */}
      {/* Tier 2 — Hubs (tabbed pages, ?tab=<slug> deep-links)         */}
      {/* ============================================================ */}
      {HUBS.map((hub) => (
        <Route
          key={hub.route}
          path={hub.route}
          element={
            <AuthenticatedLayout>
              <HubPage hub={hub} />
            </AuthenticatedLayout>
          }
        />
      ))}

      {/* Old leaf routes → hub ?tab= redirects (keep bookmarks working) */}
      {HUB_REDIRECTS.map(({ from, to }) => (
        <Route key={from} path={from} element={<Navigate to={to} replace />} />
      ))}

      {/* ============================================================ */}
      {/* Detail / child routes that hub tabs link out to              */}
      {/* ============================================================ */}
      <Route
        path="/hierarchy/:fhOrgId"
        element={
          <AuthenticatedLayout>
            <OrganizationDetailPage />
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
        path="/competitive-intel/offices/:officeCode"
        element={
          <AuthenticatedLayout>
            <OfficeDetailPage />
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

      {/* ============================================================ */}
      {/* Tier 3 — Account (avatar menu targets)                       */}
      {/* ============================================================ */}
      <Route
        path="/saved-searches"
        element={
          <AuthenticatedLayout>
            <SavedSearchesPage />
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/insights/data-quality"
        element={
          <AuthenticatedLayout>
            <AdminGuard>
              <DataQualityDashboardPage />
            </AdminGuard>
          </AuthenticatedLayout>
        }
      />
      <Route
        path="/notifications"
        element={
          <AuthenticatedLayout>
            <NotificationCenterPage />
          </AuthenticatedLayout>
        }
      />
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
