import { Box, Typography } from '@mui/material';
import { useAuth } from '@/auth/useAuth';

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <Box sx={{ p: 4 }}>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Typography variant="body1" color="text.secondary">
        Welcome back, {user?.displayName}.
      </Typography>
    </Box>
  );
}
