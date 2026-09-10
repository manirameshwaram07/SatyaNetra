import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { fetchMe, login as apiLogin, logout as apiLogout } from "../services/api";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("satyanetra_token")
  );
  const [loading, setLoading] = useState<boolean>(!!token);

  useEffect(() => {
    let cancelled = false;
    if (token) {
      fetchMe()
        .then((u) => !cancelled && setUser(u))
        .catch(() => {
          if (!cancelled) {
            apiLogout();
            setToken(null);
            setUser(null);
          }
        })
        .finally(() => !cancelled && setLoading(false));
    }
    return () => {
      cancelled = true;
    };
  }, [token]);

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiLogin(username, password);
    setToken(res.access_token);
    localStorage.setItem("satyanetra_user", JSON.stringify({ username: res.username, role: res.role }));
    try {
      const me = await fetchMe();
      setUser(me);
    } catch {
      setUser({ id: 0, username: res.username, email: "", role: res.role });
    }
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}