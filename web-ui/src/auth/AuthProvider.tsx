import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { auth, type AuthConfig, type User } from "@/api/client";

interface AuthState {
  user: User | null;
  loading: boolean;
  devMode: boolean;
  login: (provider: string) => Promise<void>;
  devLogin: () => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  devMode: false,
  login: async () => {},
  devLogin: async () => {},
  logout: async () => {},
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [devMode, setDevMode] = useState(false);

  const refresh = async () => {
    try {
      const me = await auth.me();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Check auth config first, then try to restore session
    auth.config().then((cfg: AuthConfig) => {
      setDevMode(cfg.dev_mode);
      if (cfg.dev_mode) {
        // In dev mode, auto-login
        auth.devLogin().then(({ user: u, token }) => {
          if (token) sessionStorage.setItem("clara_token", token);
          setUser(u);
          setLoading(false);
        }).catch(() => {
          setLoading(false);
        });
      } else {
        refresh();
      }
    }).catch(() => {
      // Config endpoint failed, fall back to normal auth check
      refresh();
    });
  }, []);

  const login = async (provider: string) => {
    const { url } = await auth.loginUrl(provider);
    window.location.href = url;
  };

  const devLogin = async () => {
    const { user: u, token } = await auth.devLogin();
    if (token) sessionStorage.setItem("clara_token", token);
    setUser(u);
  };

  const logout = async () => {
    await auth.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, devMode, login, devLogin, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
