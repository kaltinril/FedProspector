import { createContext, useState, useEffect, useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';
import axios from 'axios';
import * as authApi from '@/api/auth';
import type { UserProfileDto } from '@/types/auth';

export interface AuthContextType {
  user: UserProfileDto | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isOrgAdmin: boolean;
  isSystemAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextType | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserProfileDto | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshSession = useCallback(async () => {
    try {
      const session = await authApi.me();
      setUser(session);
    } catch (err) {
      // Distinguish auth failure from network error:
      // - 401/403 means the session is truly invalid → clear user
      // - Network errors (no response) may be transient → keep current state
      if (axios.isAxiosError(err) && !err.response) {
        // Network error (no response from server) — don't clear user state
        return;
      }
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refreshSession().finally(() => setIsLoading(false));
  }, [refreshSession]);

  const login = useCallback(
    async (email: string, password: string) => {
      await authApi.login({ email, password });
      await refreshSession();
    },
    [refreshSession],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const isAuthenticated = user !== null;
  const isOrgAdmin = user?.isAdmin ?? false;
  const isSystemAdmin = user?.isSystemAdmin ?? false;

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      isLoading,
      isAuthenticated,
      isOrgAdmin,
      isSystemAdmin,
      login,
      logout,
      refreshSession,
    }),
    [user, isLoading, isAuthenticated, isOrgAdmin, isSystemAdmin, login, logout, refreshSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
