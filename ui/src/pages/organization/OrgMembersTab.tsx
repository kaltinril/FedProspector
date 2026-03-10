import { useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import MenuItem from '@mui/material/MenuItem';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import AddIcon from '@mui/icons-material/Add';
import { useSnackbar } from 'notistack';

import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { useOrgMembers, useCreateInvite } from '@/queries/useOrganization';
import { useAuth } from '@/auth/useAuth';
import { formatDate } from '@/utils/dateFormatters';

const ROLE_CHIP_COLOR: Record<string, 'primary' | 'secondary' | 'default'> = {
  owner: 'primary',
  admin: 'secondary',
  member: 'default',
};

export function OrgMembersTab() {
  const { user } = useAuth();
  const { data: members, isLoading, isError, refetch } = useOrgMembers();
  const createInviteMutation = useCreateInvite();
  const { enqueueSnackbar } = useSnackbar();

  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');

  const canManage = user?.role === 'owner' || user?.role === 'admin' || user?.isOrgAdmin === true;

  function handleInvite() {
    createInviteMutation.mutate(
      { email: inviteEmail.trim(), orgRole: inviteRole },
      {
        onSuccess: () => {
          enqueueSnackbar('Invitation sent', { variant: 'success' });
          setInviteDialogOpen(false);
          setInviteEmail('');
          setInviteRole('member');
        },
        onError: () => {
          enqueueSnackbar('Failed to send invitation', { variant: 'error' });
        },
      },
    );
  }

  if (isLoading) return <LoadingState message="Loading members..." />;
  if (isError) {
    return (
      <ErrorState
        title="Failed to load members"
        message="Could not retrieve organization members."
        onRetry={() => refetch()}
      />
    );
  }
  if (!members || members.length === 0) {
    return <EmptyState title="No members" message="This organization has no members yet." />;
  }

  return (
    <Box>
      {canManage && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setInviteDialogOpen(true)}
          >
            Invite Member
          </Button>
        </Box>
      )}

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Display Name</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Joined</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {members.map((member) => (
              <TableRow key={member.userId}>
                <TableCell>
                  <Typography variant="body2">
                    {member.displayName}
                    {member.userId === user?.userId && (
                      <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                        (you)
                      </Typography>
                    )}
                  </Typography>
                </TableCell>
                <TableCell>{member.email ?? '--'}</TableCell>
                <TableCell>
                  <Chip
                    label={member.orgRole}
                    size="small"
                    color={ROLE_CHIP_COLOR[member.orgRole] ?? 'default'}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={member.isActive ? 'Active' : 'Inactive'}
                    size="small"
                    color={member.isActive ? 'success' : 'default'}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>{formatDate(member.createdAt)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Invite Dialog */}
      <Dialog
        open={inviteDialogOpen}
        onClose={() => setInviteDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Invite Member</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Email Address"
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              fullWidth
              size="small"
              autoFocus
            />
            <TextField
              label="Role"
              select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              fullWidth
              size="small"
            >
              <MenuItem value="member">Member</MenuItem>
              <MenuItem value="admin">Admin</MenuItem>
            </TextField>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setInviteDialogOpen(false)} disabled={createInviteMutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleInvite}
            disabled={!inviteEmail.trim() || createInviteMutation.isPending}
            startIcon={createInviteMutation.isPending ? <CircularProgress size={16} /> : undefined}
          >
            Send Invite
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
