import { useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Tooltip from '@mui/material/Tooltip';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useSnackbar } from 'notistack';

import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { EmptyState } from '@/components/shared/EmptyState';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { useOrgInvites, useRevokeInvite } from '@/queries/useOrganization';
import { formatDate } from '@/utils/dateFormatters';
import type { InviteDto } from '@/types/organization';

export function OrgInvitesTab() {
  const { data: invites, isLoading, isError, refetch } = useOrgInvites();
  const revokeMutation = useRevokeInvite();
  const { enqueueSnackbar } = useSnackbar();

  const [revokeTarget, setRevokeTarget] = useState<InviteDto | null>(null);

  function handleRevoke() {
    if (!revokeTarget) return;
    revokeMutation.mutate(revokeTarget.inviteId, {
      onSuccess: () => {
        enqueueSnackbar('Invite revoked', { variant: 'success' });
        setRevokeTarget(null);
      },
      onError: () => {
        enqueueSnackbar('Failed to revoke invite', { variant: 'error' });
      },
    });
  }

  if (isLoading) return <LoadingState message="Loading invites..." />;
  if (isError) {
    return (
      <ErrorState
        title="Failed to load invites"
        message="Could not retrieve pending invitations."
        onRetry={() => refetch()}
      />
    );
  }
  if (!invites || invites.length === 0) {
    return (
      <EmptyState
        title="No pending invites"
        message="There are no pending invitations for this organization."
      />
    );
  }

  return (
    <Box>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Email</TableCell>
              <TableCell>Role</TableCell>
              <TableCell>Invited By</TableCell>
              <TableCell>Sent</TableCell>
              <TableCell>Expires</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {invites.map((invite) => {
              const expired = new Date(invite.expiresAt) < new Date();
              return (
                <TableRow key={invite.inviteId}>
                  <TableCell>{invite.email}</TableCell>
                  <TableCell>
                    <Chip label={invite.orgRole} size="small" />
                  </TableCell>
                  <TableCell>{invite.invitedByName ?? '--'}</TableCell>
                  <TableCell>{formatDate(invite.createdAt)}</TableCell>
                  <TableCell>
                    {formatDate(invite.expiresAt)}
                    {expired && (
                      <Chip
                        label="Expired"
                        size="small"
                        color="error"
                        variant="outlined"
                        sx={{ ml: 1 }}
                      />
                    )}
                  </TableCell>
                  <TableCell align="center">
                    <Tooltip title="Revoke invite">
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => setRevokeTarget(invite)}
                      >
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      <ConfirmDialog
        open={revokeTarget != null}
        title="Revoke Invitation"
        message={`Are you sure you want to revoke the invitation to "${revokeTarget?.email ?? ''}"?`}
        severity="warning"
        confirmText="Revoke"
        onConfirm={handleRevoke}
        onCancel={() => setRevokeTarget(null)}
        loading={revokeMutation.isPending}
      />
    </Box>
  );
}
