import { useState, useEffect } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import { useSnackbar } from 'notistack';

export function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const { enqueueSnackbar } = useSnackbar();

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      enqueueSnackbar('Connection restored', { variant: 'success' });
    };
    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [enqueueSnackbar]);

  if (isOnline) return null;

  return (
    <Box sx={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: (theme) => theme.zIndex.snackbar + 10 }}>
      <Alert severity="warning" sx={{ borderRadius: 0 }}>
        You are currently offline. Some features may be unavailable.
      </Alert>
    </Box>
  );
}
