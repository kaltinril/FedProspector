import { useState, useCallback, useRef, useEffect } from 'react';
import Box from '@mui/material/Box';
import Toolbar from '@mui/material/Toolbar';
import { useLocation } from 'react-router-dom';
import { Sidebar, SIDEBAR_WIDTH_EXPANDED, SIDEBAR_WIDTH_COLLAPSED } from '@/components/layout/Sidebar';
import { TopBar } from '@/components/layout/TopBar';

const STORAGE_KEY = 'sidebarCollapsed';

function getStoredCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [collapsed, setCollapsed] = useState(getStoredCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);
  const mainRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  // Move focus to main content area on route changes
  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true });
  }, [location.pathname]);

  const handleToggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // localStorage not available
      }
      return next;
    });
  }, []);

  const handleMobileToggle = useCallback(() => {
    setMobileOpen((prev) => !prev);
  }, []);

  const handleMobileClose = useCallback(() => {
    setMobileOpen(false);
  }, []);

  const sidebarWidth = collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED;

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Box
        component="a"
        href="#main-content"
        sx={{
          position: 'absolute',
          left: '-9999px',
          top: 'auto',
          width: '1px',
          height: '1px',
          overflow: 'hidden',
          zIndex: (theme) => theme.zIndex.tooltip + 1,
          '&:focus': {
            position: 'fixed',
            top: 8,
            left: 8,
            width: 'auto',
            height: 'auto',
            overflow: 'visible',
            bgcolor: 'primary.main',
            color: 'primary.contrastText',
            px: 2,
            py: 1,
            borderRadius: 1,
            fontSize: '0.875rem',
            fontWeight: 600,
            textDecoration: 'none',
          },
        }}
      >
        Skip to main content
      </Box>
      <TopBar
        sidebarCollapsed={collapsed}
        onMobileMenuToggle={handleMobileToggle}
      />
      <Sidebar
        collapsed={collapsed}
        onToggle={handleToggle}
        mobileOpen={mobileOpen}
        onMobileClose={handleMobileClose}
      />
      <Box
        ref={mainRef}
        id="main-content"
        component="main"
        tabIndex={-1}
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${sidebarWidth}px)` },
          ml: { md: `${sidebarWidth}px` },
          transition: 'width 225ms cubic-bezier(0.4, 0, 0.6, 1), margin-left 225ms cubic-bezier(0.4, 0, 0.6, 1)',
          outline: 'none',
        }}
      >
        {/* Spacer for fixed AppBar */}
        <Toolbar />
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}
