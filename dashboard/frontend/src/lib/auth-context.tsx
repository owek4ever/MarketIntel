"use client";
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { authApi, setAccessToken } from "@/lib/api";

interface User { id: string; email: string; role: string; is_active: boolean }
interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>({} as AuthCtx);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount: try to restore session from refresh token cookie
  useEffect(() => {
    const hasSession = localStorage.getItem("has_session");
    if (!hasSession) { setLoading(false); return; }
    
    authApi.refresh()
      .then(({ data }) => {
        setAccessToken(data.access_token);
        return authApi.me();
      })
      .then(({ data }) => setUser(data))
      .catch(() => localStorage.removeItem("has_session"))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const { data } = await authApi.login(email, password);
    setAccessToken(data.access_token);
    // Actual refresh token comes back as HttpOnly cookie, we just store a flag
    localStorage.setItem("has_session", "1");
    const me = await authApi.me();
    setUser(me.data);
  };

  const logout = async () => {
    try { await authApi.logout(); } catch { /* ignore */ }
    setAccessToken(null);
    localStorage.removeItem("has_session");
    setUser(null);
  };

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}
