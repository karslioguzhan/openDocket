import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
import type { User } from "./types";

export type Theme = "light" | "dark";

interface ThemeState {
  theme: Theme;
  toggle: () => Promise<void>;
}

const STORAGE_KEY = "opendocket_theme";

function initialTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY);
  return saved === "dark" ? "dark" : "light";
}

const ThemeContext = createContext<ThemeState>({
  theme: "light",
  toggle: async () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { user, refresh } = useAuth();
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (user && (user.theme === "light" || user.theme === "dark")) {
      setTheme(user.theme);
    }
  }, [user]);

  const toggle = useCallback(async () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      await api<User>("/users/me/theme", {
        method: "PATCH",
        body: JSON.stringify({ theme: next }),
      });
      await refresh();
    } catch {
      // Keep the local value; the server will catch up on the next change.
    }
  }, [theme, refresh]);

  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
