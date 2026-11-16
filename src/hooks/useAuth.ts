import { useState, useCallback } from "react";
import { login as apiLogin } from "../api";

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);

  const login = useCallback(async (u: string, p: string): Promise<void> => {
    try {
      const data = await apiLogin(u, p) as { access_token?: string };
      if (data.access_token) {
        setToken(data.access_token);
        setUsername(u);
        return;
      }
      throw new Error("Invalid credentials");
    } catch (err) {
      if (err instanceof TypeError) {
        // Network failure. On the live site, say so — never fall back to a fake
        // "demo" login whose changes silently go nowhere.
        if (import.meta.env.VITE_API_BASE_URL) {
          throw new Error(
            "Can't reach the server. It may be waking up — wait about a minute and try again."
          );
        }
        // Local dev without a backend: allow the offline demo login.
        if (u === "admin" && p === "bits2024") {
          setToken("demo-token");
          setUsername(u);
          return;
        }
        throw new Error("Invalid credentials");
      }
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUsername(null);
  }, []);

  return { token, username, isAdmin: token !== null, login, logout };
}
