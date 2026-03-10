import type { ReactNode } from 'react';
import { Box, Typography } from '@mui/material';
import { useAuth } from '@/auth/useAuth';

interface AdminGuardProps {
  children: ReactNode;
}

export function AdminGuard({ children }: AdminGuardProps) {
  const { isSystemAdmin } = useAuth();

  if (!isSystemAdmin) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
          gap: 2,
        }}
      >
        <Typography variant="h4">Access Denied</Typography>
        <Typography variant="body1" color="text.secondary">
          You do not have permission to view this page.
        </Typography>
      </Box>
    );
  }

  return <>{children}</>;
}
