import { Suspense } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Box, CircularProgress, CssBaseline } from '@mui/material';
import { AuthProvider } from '@/auth/AuthContext';
import { AppRoutes } from '@/routes';

function LoadingFallback() {
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
      }}
    >
      <CircularProgress size={48} />
    </Box>
  );
}

function App() {
  return (
    <BrowserRouter>
      <CssBaseline />
      <AuthProvider>
        <Suspense fallback={<LoadingFallback />}>
          <AppRoutes />
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
