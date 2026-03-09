import { useState, useCallback } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import AddIcon from '@mui/icons-material/Add';
import { useSnackbar } from 'notistack';

import { useCreateOrganization, useCreateOrganizationOwner } from '@/queries/useAdmin';
import type { CreateOrganizationRequest, CreateOwnerRequest } from '@/types/api';

export default function OrganizationsTab() {
  const { enqueueSnackbar } = useSnackbar();
  const createOrg = useCreateOrganization();
  const createOwner = useCreateOrganizationOwner();

  // Create Organization dialog
  const [orgDialogOpen, setOrgDialogOpen] = useState(false);
  const [orgForm, setOrgForm] = useState<CreateOrganizationRequest>({ name: '', slug: '' });

  // Create Owner dialog
  const [ownerDialogOpen, setOwnerDialogOpen] = useState(false);
  const [ownerOrgId, setOwnerOrgId] = useState<number | null>(null);
  const [ownerForm, setOwnerForm] = useState<CreateOwnerRequest>({
    email: '',
    displayName: '',
    password: '',
  });

  const handleCreateOrg = useCallback(() => {
    createOrg.mutate(orgForm, {
      onSuccess: () => {
        enqueueSnackbar('Organization created successfully', { variant: 'success' });
        setOrgDialogOpen(false);
        setOrgForm({ name: '', slug: '' });
      },
      onError: () => {
        enqueueSnackbar('Failed to create organization', { variant: 'error' });
      },
    });
  }, [orgForm, createOrg, enqueueSnackbar]);

  const handleCreateOwner = useCallback(() => {
    if (ownerOrgId == null) return;
    createOwner.mutate(
      { orgId: ownerOrgId, data: ownerForm },
      {
        onSuccess: () => {
          enqueueSnackbar('Organization owner created successfully', { variant: 'success' });
          setOwnerDialogOpen(false);
          setOwnerForm({ email: '', displayName: '', password: '' });
          setOwnerOrgId(null);
        },
        onError: () => {
          enqueueSnackbar('Failed to create owner', { variant: 'error' });
        },
      },
    );
  }, [ownerOrgId, ownerForm, createOwner, enqueueSnackbar]);

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOrgDialogOpen(true)}
        >
          Create Organization
        </Button>
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          onClick={() => {
            setOwnerOrgId(null);
            setOwnerDialogOpen(true);
          }}
        >
          Create Organization Owner
        </Button>
      </Box>

      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="body1" color="text.secondary">
          Organization listing will be available once the list endpoint is implemented.
          Use the buttons above to create new organizations and assign owners.
        </Typography>
      </Paper>

      {/* Create Organization Dialog */}
      <Dialog
        open={orgDialogOpen}
        onClose={() => setOrgDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create Organization</DialogTitle>
        <DialogContent>
          <TextField
            label="Organization Name"
            value={orgForm.name ?? ''}
            onChange={(e) => setOrgForm((prev) => ({ ...prev, name: e.target.value }))}
            fullWidth
            margin="normal"
            required
          />
          <TextField
            label="Slug"
            value={orgForm.slug ?? ''}
            onChange={(e) =>
              setOrgForm((prev) => ({
                ...prev,
                slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'),
              }))
            }
            fullWidth
            margin="normal"
            required
            helperText="URL-friendly identifier (lowercase letters, numbers, hyphens)"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOrgDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreateOrg}
            disabled={!orgForm.name || !orgForm.slug || createOrg.isPending}
          >
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create Owner Dialog */}
      <Dialog
        open={ownerDialogOpen}
        onClose={() => setOwnerDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create Organization Owner</DialogTitle>
        <DialogContent>
          <TextField
            label="Organization ID"
            type="number"
            value={ownerOrgId ?? ''}
            onChange={(e) => setOwnerOrgId(parseInt(e.target.value, 10) || null)}
            fullWidth
            margin="normal"
            required
            helperText="Enter the numeric ID of the organization"
          />
          <TextField
            label="Email"
            type="email"
            value={ownerForm.email ?? ''}
            onChange={(e) => setOwnerForm((prev) => ({ ...prev, email: e.target.value }))}
            fullWidth
            margin="normal"
            required
          />
          <TextField
            label="Display Name"
            value={ownerForm.displayName ?? ''}
            onChange={(e) => setOwnerForm((prev) => ({ ...prev, displayName: e.target.value }))}
            fullWidth
            margin="normal"
            required
          />
          <TextField
            label="Password"
            type="password"
            value={ownerForm.password ?? ''}
            onChange={(e) => setOwnerForm((prev) => ({ ...prev, password: e.target.value }))}
            fullWidth
            margin="normal"
            required
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOwnerDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreateOwner}
            disabled={
              ownerOrgId == null ||
              !ownerForm.email ||
              !ownerForm.displayName ||
              !ownerForm.password ||
              createOwner.isPending
            }
          >
            Create Owner
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
