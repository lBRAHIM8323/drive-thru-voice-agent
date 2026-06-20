import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { clearToken, getToken, onUnauthorized, setToken } from '../../api/client';
import { useMe } from '../../api/hooks';
import type { User } from '../../api/types';

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(getToken);
  const qc = useQueryClient();

  const { data, isLoading } = useMe();

  function handleUnauthorized() {
    setTokenState(null);
    qc.clear();
  }

  useEffect(() => {
    onUnauthorized(handleUnauthorized);
  }, []);

  const user = data ?? null;

  function login(token: string) {
    setToken(token);
    setTokenState(token);
  }

  function logout() {
    clearToken();
    setTokenState(null);
    qc.clear();
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading: isLoading && !!token,
        isAuthenticated: !!token && !!user,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
