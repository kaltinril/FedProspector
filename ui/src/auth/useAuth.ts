import { useContext } from 'react';
import { AuthContext } from '@/auth/AuthContext';
import type { AuthContextType } from '@/auth/AuthContext';

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
