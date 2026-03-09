import { useState, useCallback } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import AddIcon from '@mui/icons-material/Add';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import { useSnackbar } from 'notistack';

import { useCreateOrganization, useCreateOrganizationOwner, useListOrganizations } from '@/queries/useAdmin';
import type { CreateOrganizationRequest, CreateOwnerRequest } from '@/types/api';

export default function OrganizationsTab() {
  const { enqueueSnackbar } = useSnackbar();
  const { data: orgs, isLoading, isError } = useListOrganizations();
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
      onError: (error: any) => {
        const msg = error?.response?.data?.error || 'Failed to create organization';
        enqueueSnackbar(msg, { variant: 'error' });
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
        onError: (error: any) => {
          const msg = error?.response?.data?.error || 'Failed to create owner';
          enqueueSnackbar(msg, { variant: 'error' });
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

      {isError ? (
        <Alert severity="error">Failed to load organizations</Alert>
      ) : isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Name</TableCell>
                <TableCell>Slug</TableCell>
                <TableCell>Tier</TableCell>
                <TableCell>Max Users</TableCell>
                <TableCell>Active</TableCell>
                <TableCell>Created</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {orgs && orgs.length > 0 ? (
                orgs.map((org) => (
                  <TableRow key={org.id}>
                    <TableCell>{org.id}</TableCell>
                    <TableCell>{org.name}</TableCell>
                    <TableCell>{org.slug}</TableCell>
                    <TableCell>{org.subscriptionTier ?? '—'}</TableCell>
                    <TableCell>{org.maxUsers}</TableCell>
                    <TableCell>
                      <Chip
                        label={org.isActive ? 'Active' : 'Inactive'}
                        color={org.isActive ? 'success' : 'default'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>{new Date(org.createdAt).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        startIcon={<PersonAddIcon />}
                        onClick={() => {
                          setOwnerOrgId(org.id);
                          setOwnerDialogOpen(true);
                        }}
                      >
                        Add Owner
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={8} align="center">
                    <Typography color="text.secondary">No organizations found.</Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

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
            inputProps={{ minLength: 2, maxLength: 100 }}
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
            inputProps={{ minLength: 2, maxLength: 50, pattern: '[a-z0-9-]+' }}
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
            label="Organization"
            select
            value={ownerOrgId ?? ''}
            onChange={(e) => setOwnerOrgId(e.target.value ? Number(e.target.value) : null)}
            fullWidth
            margin="normal"
            required
          >
            {orgs?.map((org) => (
              <MenuItem key={org.id} value={org.id}>
                {org.name} ({org.slug})
              </MenuItem>
            ))}
          </TextField>
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
            inputProps={{ minLength: 2, maxLength: 100 }}
          />
          <TextField
            label="Password"
            type="password"
            value={ownerForm.password ?? ''}
            onChange={(e) => setOwnerForm((prev) => ({ ...prev, password: e.target.value }))}
            fullWidth
            margin="normal"
            required
            inputProps={{ minLength: 8 }}
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
