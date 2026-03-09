import { useState, useCallback, useRef, useEffect } from 'react';
import Box from '@mui/material/Box';
import Toolbar from '@mui/material/Toolbar';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useLocation } from 'react-router-dom';
import { Sidebar, SIDEBAR_WIDTH_EXPANDED, SIDEBAR_WIDTH_COLLAPSED } from '@/components/layout/Sidebar';
import { TopBar } from '@/components/layout/TopBar';

const STORAGE_KEY = 'sidebarCollapsed';
const FADE_DURATION_MS = 150;

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
  const [visible, setVisible] = useState(true);
  const mainRef = useRef<HTMLDivElement>(null);
  const prevPathRef = useRef<string | null>(null);
  const location = useLocation();
  const prefersReducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');

  // Fade transition on route changes
  useEffect(() => {
    // Skip on initial mount or when reduced motion is preferred
    if (prevPathRef.current === null || prefersReducedMotion) {
      prevPathRef.current = location.pathname;
      mainRef.current?.focus({ preventScroll: true });
      return;
    }

    if (prevPathRef.current !== location.pathname) {
      prevPathRef.current = location.pathname;
      setVisible(false);
      const timer = setTimeout(() => {
        setVisible(true);
        mainRef.current?.focus({ preventScroll: true });
      }, FADE_DURATION_MS);
      return () => clearTimeout(timer);
    }
  }, [location.pathname, prefersReducedMotion]);

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
          '@media (prefers-reduced-motion: reduce)': {
            transition: 'none',
          },
          outline: 'none',
        }}
      >
        {/* Spacer for fixed AppBar */}
        <Toolbar />
        <Box
          sx={{
            p: 3,
            opacity: visible ? 1 : 0,
            transition: prefersReducedMotion
              ? 'none'
              : `opacity ${FADE_DURATION_MS}ms ease-in-out`,
          }}
        >
          {children}
        </Box>
      </Box>
    </Box>
  );
}
