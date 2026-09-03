import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  fetchAuthStatus,
  fetchMe,
  getAccessToken,
  loginUser,
  logoutUser,
  registerUser,
  type AuthUser,
} from "./api";

interface AuthState {
  user: AuthUser | null;
  authEnabled: boolean;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authEnabled, setAuthEnabled] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    fetchAuthStatus()
      .then(async (status) => {
        setAuthEnabled(status.auth_enabled);
        if (status.auth_enabled && getAccessToken()) {
          try {
            setUser(await fetchMe());
          } catch {
            // Stale token — request() already cleared it.
            setUser(null);
          }
        }
      })
      .catch(() => {
        // API unreachable; pages will surface their own errors.
      })
      .finally(() => setReady(true));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await loginUser(email, password);
    setUser(await fetchMe());
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    await registerUser(email, password);
    setUser(await fetchMe());
  }, []);

  const logout = useCallback(async () => {
    await logoutUser();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, authEnabled, ready, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

const ROLE_LEVELS: Record<string, number> = { viewer: 1, operator: 2, admin: 3 };

/** Client-side UI gating (backend always enforces for real). */
export function useMinRole(level: string): boolean {
  const { user, authEnabled } = useAuth();
  if (!authEnabled) return true;
  if (!user) return false;
  return (ROLE_LEVELS[user.role] ?? 0) >= (ROLE_LEVELS[level] ?? 99);
}
