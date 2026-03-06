import { lazy } from 'react';
import { Route, Routes, Navigate } from 'react-router-dom';
import { AuthGuard } from '@/auth/AuthGuard';
import { AppLayout } from '@/components/layout/AppLayout';

const LoginPage = lazy(() => import('@/pages/login/LoginPage'));
const RegisterPage = lazy(() => import('@/pages/login/RegisterPage'));
const DashboardPage = lazy(() => import('@/pages/dashboard/DashboardPage'));
const SetupPage = lazy(() => import('@/pages/setup/SetupPage'));

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

      {/* Default redirect */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
