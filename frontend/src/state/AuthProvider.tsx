import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AuthContext } from "../hooks/useAuth";
import { api, onUnauthorized } from "../services/api";
import { useToast } from "../hooks/useToast";
import type { User } from "../types";

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  // Restore session on load/refresh by asking the backend who (if anyone)
  // the session cookie belongs to. A 401 here just means "not logged in" -
  // it's the expected state for every anonymous dashboard visitor, not an
  // error to surface.
  useEffect(() => {
    let mounted = true;
    api
      .auth.me()
      .then((u) => mounted && setUser(u))
      .catch(() => mounted && setUser(null))
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, []);

  // Any request anywhere in the app coming back 401 (e.g. the session
  // expired mid-visit) clears local auth state so protected UI reacts
  // immediately instead of continuing to believe it's authenticated.
  useEffect(() => onUnauthorized(() => setUser(null)), []);

  const login = useCallback(async (username: string, password: string) => {
    const loggedInUser = await api.auth.login(username, password);
    setUser(loggedInUser);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } finally {
      setUser(null);
      toast.info("Signed out");
    }
  }, [toast]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isAdmin: user?.role === "admin",
        loading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
