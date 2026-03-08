import { lazy } from 'react';
import { Route, Routes, Navigate } from 'react-router-dom';
import { AuthGuard } from '@/auth/AuthGuard';
import { AppLayout } from '@/components/layout/AppLayout';

const LoginPage = lazy(() => import('@/pages/login/LoginPage'));
const RegisterPage = lazy(() => import('@/pages/login/RegisterPage'));
const DashboardPage = lazy(() => import('@/pages/dashboard/DashboardPage'));
const SetupPage = lazy(() => import('@/pages/setup/SetupPage'));
const OpportunitySearchPage = lazy(
  () => import('@/pages/opportunities/OpportunitySearchPage'),
);
const TargetOpportunityPage = lazy(
  () => import('@/pages/opportunities/TargetOpportunityPage'),
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

function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppLayout>{children}</AppLayout>
    </AuthGuard>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

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

      {/* Default redirect */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
