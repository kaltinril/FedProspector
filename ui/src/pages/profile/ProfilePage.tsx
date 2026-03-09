import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import Chip from '@mui/material/Chip';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import { useSnackbar } from 'notistack';

import { PageHeader } from '@/components/shared/PageHeader';
import { useAuth } from '@/auth/useAuth';
import * as authApi from '@/api/auth';
import { formatDate } from '@/utils/dateFormatters';

export default function ProfilePage() {
  const { user, refreshSession } = useAuth();
  const { enqueueSnackbar } = useSnackbar();
  const navigate = useNavigate();

  // Profile edit state
  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState(user?.displayName ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  // Password state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  function handleEditStart() {
    setDisplayName(user?.displayName ?? '');
    setEmail(user?.email ?? '');
    setProfileError(null);
    setEditing(true);
  }

  function handleEditCancel() {
    setEditing(false);
    setProfileError(null);
  }

  async function handleProfileSave() {
    setProfileSaving(true);
    setProfileError(null);
    try {
      await authApi.updateProfile({
        displayName: displayName.trim() || null,
        email: email.trim() || null,
      });
      await refreshSession();
      setEditing(false);
      enqueueSnackbar('Profile updated', { variant: 'success' });
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to update profile';
      setProfileError(msg);
    } finally {
      setProfileSaving(false);
    }
  }

  function passwordValid(): boolean {
    return (
      currentPassword.length > 0 &&
      newPassword.length >= 8 &&
      newPassword === confirmPassword
    );
  }

  async function handleChangePassword() {
    setPasswordSaving(true);
    setPasswordError(null);
    try {
      await authApi.changePassword({ currentPassword, newPassword });
      enqueueSnackbar('Password changed. Please log in again.', {
        variant: 'success',
      });
      navigate('/login');
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to change password';
      setPasswordError(msg);
    } finally {
      setPasswordSaving(false);
    }
  }

  if (!user) return null;

  return (
    <Box>
      <PageHeader title="Profile" subtitle="Manage your account settings" />

      {/* Profile Info Card */}
      <Card sx={{ mb: 3 }}>
        <CardHeader
          title="Profile Information"
          action={
            !editing ? (
              <Button variant="outlined" size="small" onClick={handleEditStart}>
                Edit
              </Button>
            ) : undefined
          }
        />
        <CardContent>
          {profileError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {profileError}
            </Alert>
          )}

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: { xs: '100%', sm: 480 } }}>
            <TextField
              label="Username"
              value={user.username}
              disabled
              fullWidth
              size="small"
            />
            <TextField
              label="Display Name"
              value={editing ? displayName : user.displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              disabled={!editing}
              fullWidth
              size="small"
            />
            <TextField
              label="Email"
              value={editing ? email : user.email ?? ''}
              onChange={(e) => setEmail(e.target.value)}
              disabled={!editing}
              fullWidth
              size="small"
              type="email"
            />

            {editing && (
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button
                  variant="contained"
                  onClick={handleProfileSave}
                  disabled={profileSaving}
                >
                  Save
                </Button>
                <Button
                  variant="outlined"
                  onClick={handleEditCancel}
                  disabled={profileSaving}
                >
                  Cancel
                </Button>
              </Box>
            )}
          </Box>

          <Box sx={{ mt: 3, display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" color="text.secondary">
                Role:
              </Typography>
              <Chip label={user.role} size="small" color="primary" variant="outlined" />
            </Box>
            <Typography variant="body2" color="text.secondary">
              Created: {formatDate(user.createdAt)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Last login: {formatDate(user.lastLoginAt)}
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* Change Password Card */}
      <Card>
        <CardHeader title="Change Password" />
        <CardContent>
          {passwordError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {passwordError}
            </Alert>
          )}

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: { xs: '100%', sm: 480 } }}>
            <TextField
              label="Current Password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              fullWidth
              size="small"
              autoComplete="current-password"
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
            <Box>
              <Button
                variant="contained"
                onClick={handleChangePassword}
                disabled={!passwordValid() || passwordSaving}
              >
                Change Password
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}
