import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Skeleton from '@mui/material/Skeleton';
import Typography from '@mui/material/Typography';

interface LoadingStateProps {
  variant?: 'skeleton' | 'spinner' | 'overlay';
  rows?: number;
  message?: string;
}

export function LoadingState({
  variant = 'spinner',
  rows = 5,
  message,
}: LoadingStateProps) {
  if (variant === 'skeleton') {
    return (
      <Box sx={{ width: '100%' }}>
        {Array.from({ length: rows }, (_, i) => (
          <Skeleton
            key={i}
            variant="rectangular"
            height={40}
            sx={{ mb: 1, borderRadius: 1 }}
          />
        ))}
      </Box>
    );
  }

  if (variant === 'overlay') {
    return (
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'rgba(0, 0, 0, 0.3)',
          zIndex: 10,
          borderRadius: 1,
        }}
      >
        <CircularProgress />
        {message && (
          <Typography variant="body2" sx={{ mt: 2, color: 'common.white' }}>
            {message}
          </Typography>
        )}
      </Box>
    );
  }

  // spinner (default)
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        py: 8,
      }}
    >
      <CircularProgress />
      {message && (
        <Typography
          variant="body2"
          sx={{
            color: "text.secondary",
            mt: 2
          }}>
          {message}
        </Typography>
      )}
    </Box>
  );
}
