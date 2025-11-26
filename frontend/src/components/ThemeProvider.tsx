import { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: Theme;
}

interface ThemeProviderState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeProviderContext = createContext<ThemeProviderState | undefined>(undefined);

export function ThemeProvider({ children, defaultTheme = "light" }: ThemeProviderProps) {
  const [theme] = useState<Theme>("light");

  useEffect(() => {
    const root = document.documentElement;
    // Always ensure dark class is removed to force light theme
    root.classList.remove("dark");
    // Clear any theme stored in localStorage to prevent confusion
    localStorage.removeItem("theme");
  }, []);

  const value = {
    theme,
    setTheme: () => {
      // Disable theme switching - always stay on light
    },
  };

  return (
    <ThemeProviderContext.Provider value={value}>
      {children}
    </ThemeProviderContext.Provider>
  );
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
};