import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import axios from 'axios';

import { useAuth } from '@/auth/useAuth';
import * as authApi from '@/api/auth';

export default function ChangePasswordPage() {
  const { isAuthenticated, forcePasswordChange, logout, clearSession } = useAuth();
  const navigate = useNavigate();

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Use <Navigate> instead of navigate() during render to avoid React warnings
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!forcePasswordChange) {
    return <Navigate to="/dashboard" replace />;
  }

  function passwordValid(): boolean {
    return (
      currentPassword.length > 0 &&
      newPassword.length >= 8 &&
      newPassword === confirmPassword
    );
  }

  async function handleChangePassword() {
    setSaving(true);
    setError(null);
    try {
      await authApi.changePassword({ currentPassword, newPassword });
      // Password changed — server revoked all sessions.
      // Clear local auth state (don't call logout API — session is already dead).
      // This sets user to null, which triggers the Navigate to /login above.
      clearSession();
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data as { error?: string; message?: string };
        setError(data.error ?? data.message ?? 'Failed to change password');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to change password');
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleLogout() {
    try {
      await logout();
    } catch {
      // Ignore — just redirect
    }
    navigate('/login', { replace: true });
  }

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        bgcolor: 'background.default',
        px: 2,
      }}
    >
      <Card sx={{ maxWidth: 480, width: '100%' }}>
        <CardContent sx={{ p: { xs: 2, sm: 4 } }}>
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <Typography variant="h4" component="h1" fontWeight={700}>
              FedProspect
            </Typography>
          </Box>

          <Alert severity="warning" sx={{ mb: 3 }}>
            You must change your password before continuing. This is required by
            your administrator.
          </Alert>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            <TextField
              label="Current Password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              fullWidth
              size="small"
              autoComplete="current-password"
              autoFocus
            />
            <TextField
              label="New Password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              fullWidth
              size="small"
              autoComplete="new-password"
              helperText="Minimum 8 characters"
              error={newPassword.length > 0 && newPassword.length < 8}
            />
            <TextField
              label="Confirm New Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              fullWidth
              size="small"
              autoComplete="new-password"
              error={
                confirmPassword.length > 0 && confirmPassword !== newPassword
              }
              helperText={
                confirmPassword.length > 0 && confirmPassword !== newPassword
                  ? 'Passwords do not match'
                  : undefined
              }
            />
            <Button
              variant="contained"
              fullWidth
              size="large"
              onClick={handleChangePassword}
              disabled={!passwordValid() || saving}
            >
              Change Password
            </Button>
            <Button
              variant="text"
              size="small"
              onClick={handleLogout}
              sx={{ alignSelf: 'center' }}
            >
              Log out instead
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
