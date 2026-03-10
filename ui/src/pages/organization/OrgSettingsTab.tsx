import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import { useSnackbar } from 'notistack';

import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { useOrganization, useUpdateOrganization } from '@/queries/useOrganization';
import { useAuth } from '@/auth/useAuth';
import { formatDate } from '@/utils/dateFormatters';

export function OrgSettingsTab() {
  const { user } = useAuth();
  const { data: org, isLoading, isError, refetch } = useOrganization();
  const updateMutation = useUpdateOrganization();
  const { enqueueSnackbar } = useSnackbar();

  const [name, setName] = useState('');
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Determine if user can edit (owner or admin role)
  const canEdit = user?.role === 'owner' || user?.role === 'admin' || user?.isOrgAdmin === true;

  function handleEditStart() {
    setName(org?.name ?? '');
    setError(null);
    setEditing(true);
  }

  function handleCancel() {
    setEditing(false);
    setError(null);
  }

  function handleSave() {
    setError(null);
    updateMutation.mutate(
      { name: name.trim() || null },
      {
        onSuccess: () => {
          setEditing(false);
          enqueueSnackbar('Organization updated', { variant: 'success' });
        },
        onError: (err) => {
          const msg = err instanceof Error ? err.message : 'Failed to update organization';
          setError(msg);
          enqueueSnackbar('Failed to update organization', { variant: 'error' });
        },
      },
    );
  }

  if (isLoading) return <LoadingState message="Loading organization..." />;
  if (isError) {
    return (
      <ErrorState
        title="Failed to load organization"
        message="Could not retrieve organization details."
        onRetry={() => refetch()}
      />
    );
  }
  if (!org) return null;

  return (
    <Box sx={{ maxWidth: 600 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1 }}>
          <TextField
            label="Organization Name"
            value={editing ? name : org.name}
            onChange={(e) => setName(e.target.value)}
            disabled={!editing}
            fullWidth
            size="small"
          />
          {canEdit && !editing && (
            <Button variant="outlined" size="small" onClick={handleEditStart} sx={{ flexShrink: 0 }}>
              Edit
            </Button>
          )}
        </Box>

        {editing && (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="contained"
              onClick={handleSave}
              disabled={updateMutation.isPending}
            >
              Save
            </Button>
            <Button
              variant="outlined"
              onClick={handleCancel}
              disabled={updateMutation.isPending}
            >
              Cancel
            </Button>
          </Box>
        )}

        <TextField
          label="Slug"
          value={org.slug}
          disabled
          fullWidth
          size="small"
        />

        <Typography variant="body2" color="text.secondary">
          Max Users: {org.maxUsers}
        </Typography>
        {org.subscriptionTier && (
          <Typography variant="body2" color="text.secondary">
            Subscription: {org.subscriptionTier}
          </Typography>
        )}
        <Typography variant="body2" color="text.secondary">
          Created: {formatDate(org.createdAt)}
        </Typography>
      </Box>
    </Box>
  );
}
