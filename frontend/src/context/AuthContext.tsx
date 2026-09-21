import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { Credentials, Session } from "../types";
import * as authApi from "../api/auth";
import { registerAuthHandlers } from "../api/client";
import { clearSession, loadSession, saveSession } from "../storage";

interface AuthContextValue {
  session: Session | null;
  login: (creds: Credentials) => Promise<void>;
  register: (creds: Credentials) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => loadSession());

  // Mirror the latest session in a ref so the api client's auth handlers
  // (registered once) always read current tokens, not a stale closure.
  const sessionRef = useRef(session);
  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  const login = useCallback(async (creds: Credentials) => {
    const s = await authApi.login(creds);
    saveSession(s);
    setSession(s);
  }, []);

  const register = useCallback(async (creds: Credentials) => {
    const s = await authApi.register(creds);
    saveSession(s);
    setSession(s);
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setSession(null);
  }, []);

  // Let the api client refresh tokens (and force logout) on 401s.
  useEffect(() => {
    registerAuthHandlers({
      getSession: () => sessionRef.current,
      onTokensRefreshed: (accessToken, refreshToken) => {
        setSession((prev) => {
          if (!prev) return prev;
          const next = { ...prev, accessToken, refreshToken };
          saveSession(next);
          return next;
        });
      },
      onAuthFailure: logout,
    });
    return () => registerAuthHandlers(null);
  }, [logout]);

  const value = useMemo(
    () => ({ session, login, register, logout }),
    [session, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
