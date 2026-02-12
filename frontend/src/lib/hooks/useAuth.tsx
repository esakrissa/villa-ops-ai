"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from "react";
import {
  getMe,
  logout as authLogout,
  isAuthenticated,
} from "@/lib/auth";
import type { User } from "@/lib/auth";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  setUser: (user: User | null) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const me = await getMe();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated()) {
      refreshUser();
    } else {
      setLoading(false);
    }
  }, [refreshUser]);

  const logout = useCallback(() => {
    authLogout();
    setUser(null);
  }, []);

  const contextValue = useMemo(
    () => ({ user, loading, setUser, logout, refreshUser }),
    [user, loading, logout, refreshUser],
  );

  return <AuthContext value={contextValue}>{children}</AuthContext>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
