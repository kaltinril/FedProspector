import { useContext } from 'react';
import { ThemeContext } from '@/theme/ThemeContext';
import type { ThemeContextType } from '@/theme/ThemeContext';

export function useThemeMode(): ThemeContextType {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useThemeMode must be used within a ThemeProvider');
  }
  return context;
}
