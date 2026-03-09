import { useState, useCallback } from 'react';
import Box from '@mui/material/Box';
import Switch from '@mui/material/Switch';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import type { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import type { SelectChangeEvent } from '@mui/material/Select';
import { useSnackbar } from 'notistack';

import { useAdminUsers, useUpdateUser, useResetUserPassword } from '@/queries/useAdmin';
import { DataTable } from '@/components/shared/DataTable';
import { LoadingState } from '@/components/shared/LoadingState';
import { ErrorState } from '@/components/shared/ErrorState';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';
import { formatDateTime } from '@/utils/dateFormatters';
import type { UserListDto } from '@/types/api';

export default function UserManagementTab() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [confirmResetUser, setConfirmResetUser] = useState<UserListDto | null>(null);
  const [tempPassword, setTempPassword] = useState<string | null>(null);

  const { enqueueSnackbar } = useSnackbar();
  const { data, isLoading, isError, refetch } = useAdminUsers({ page, pageSize });
  const updateUser = useUpdateUser();
  const resetPassword = useResetUserPassword();

  const handleToggleActive = useCallback(
    (user: UserListDto) => {
      updateUser.mutate(
        { id: user.userId, data: { isActive: !user.isActive } },
        {
          onSuccess: () => {
            enqueueSnackbar(`User ${user.username} ${user.isActive ? 'deactivated' : 'activated'}`, {
              variant: 'success',
            });
          },
          onError: () => {
            enqueueSnackbar('Failed to update user', { variant: 'error' });
          },
        },
      );
    },
    [updateUser, enqueueSnackbar],
  );

  const handleRoleChange = useCallback(
    (user: UserListDto, role: string) => {
      updateUser.mutate(
        { id: user.userId, data: { role, isAdmin: role === 'ADMIN' } },
        {
          onSuccess: () => {
            enqueueSnackbar(`Role updated for ${user.username}`, { variant: 'success' });
          },
          onError: () => {
            enqueueSnackbar('Failed to update role', { variant: 'error' });
          },
        },
      );
    },
    [updateUser, enqueueSnackbar],
  );

  const handleConfirmReset = useCallback(() => {
    if (!confirmResetUser) return;
    resetPassword.mutate(confirmResetUser.userId, {
      onSuccess: (resp) => {
        setConfirmResetUser(null);
        setTempPassword(resp.message);
      },
      onError: () => {
        enqueueSnackbar('Failed to reset password', { variant: 'error' });
        setConfirmResetUser(null);
      },
    });
  }, [confirmResetUser, resetPassword, enqueueSnackbar]);

  const handleCopyPassword = useCallback(() => {
    if (tempPassword) {
      void navigator.clipboard.writeText(tempPassword);
      enqueueSnackbar('Password copied to clipboard', { variant: 'info' });
    }
  }, [tempPassword, enqueueSnackbar]);

  const handlePaginationChange = useCallback((model: GridPaginationModel) => {
    setPage(model.page + 1);
    setPageSize(model.pageSize);
  }, []);

  const columns: GridColDef<UserListDto>[] = [
    { field: 'username', headerName: 'Username', width: 140 },
    { field: 'displayName', headerName: 'Display Name', width: 160 },
    { field: 'email', headerName: 'Email', width: 200 },
    {
      field: 'role',
      headerName: 'Role',
      width: 130,
      renderCell: (params) => {
        const user = params.row;
        return (
          <Select
            value={user.role}
            size="small"
            variant="standard"
            onChange={(e: SelectChangeEvent) => handleRoleChange(user, e.target.value)}
            sx={{ minWidth: 90 }}
          >
            <MenuItem value="USER">USER</MenuItem>
            <MenuItem value="ADMIN">ADMIN</MenuItem>
          </Select>
        );
      },
    },
    {
      field: 'isActive',
      headerName: 'Active',
      width: 80,
      renderCell: (params) => {
        const user = params.row;
        return (
          <Switch
            checked={user.isActive}
            size="small"
            onChange={() => handleToggleActive(user)}
          />
        );
      },
    },
    {
      field: 'isAdmin',
      headerName: 'Admin',
      width: 80,
      renderCell: (params) => (params.value ? 'Yes' : 'No'),
    },
    {
      field: 'lastLoginAt',
      headerName: 'Last Login',
      width: 170,
      renderCell: (params) => formatDateTime(params.value as string | null),
    },
    {
      field: 'createdAt',
      headerName: 'Created',
      width: 130,
      renderCell: (params) => formatDateTime(params.value as string | null),
    },
    {
      field: 'actions',
      headerName: '',
      width: 130,
      sortable: false,
      renderCell: (params) => {
        const user = params.row;
        return (
          <Button
            size="small"
            variant="outlined"
            color="warning"
            onClick={(e) => {
              e.stopPropagation();
              setConfirmResetUser(user);
            }}
          >
            Reset Password
          </Button>
        );
      },
    },
  ];

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => refetch()} />;

  return (
    <Box>
      <DataTable
        columns={columns}
        rows={data.items}
        getRowId={(row: UserListDto) => row.userId}
        rowCount={data.totalCount}
        paginationModel={{ page: page - 1, pageSize }}
        onPaginationModelChange={handlePaginationChange}
      />

      {/* Reset Password Confirmation */}
      <ConfirmDialog
        open={confirmResetUser != null}
        title="Reset Password"
        message={`Are you sure you want to reset the password for ${confirmResetUser?.username ?? ''}? A temporary password will be generated.`}
        confirmText="Reset"
        severity="warning"
        onConfirm={handleConfirmReset}
        onCancel={() => setConfirmResetUser(null)}
        loading={resetPassword.isPending}
      />

      {/* Temporary Password Dialog */}
      <Dialog open={tempPassword != null} onClose={() => setTempPassword(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Password Reset Successful</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Share this temporary password with the user securely. They will be required to change it on
            next login.
          </Typography>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              p: 2,
              bgcolor: 'grey.100',
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '1.1rem',
            }}
          >
            <Typography sx={{ fontFamily: 'monospace', flexGrow: 1 }}>
              {tempPassword}
            </Typography>
            <Tooltip title="Copy to clipboard">
              <IconButton size="small" onClick={handleCopyPassword}>
                <ContentCopyIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
          <Typography variant="caption" color="warning.main" sx={{ mt: 1, display: 'block' }}>
            This password will not be shown again. Make sure to copy it before closing this dialog.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button variant="contained" onClick={() => setTempPassword(null)}>
            Done
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
