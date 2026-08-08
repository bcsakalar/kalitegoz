"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";

interface ThemeCtx {
  theme: Theme;
  resolved: "light" | "dark";
  setTheme: (t: Theme) => void;
}

const Ctx = createContext<ThemeCtx>({ theme: "system", resolved: "light", setTheme: () => {} });
export const useTheme = () => useContext(Ctx);

const KEY = "kg_theme";

function systemDark() {
  return typeof window !== "undefined"
    && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export default function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("system");
  const [resolved, setResolved] = useState<"light" | "dark">("light");

  const apply = useCallback((t: Theme) => {
    const root = document.documentElement;
    const isDark = t === "dark" || (t === "system" && systemDark());
    // "system" seciliyken data-theme KALDIRILIR ki CSS'teki
    // prefers-color-scheme kurali devreye girsin.
    if (t === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", t);
    setResolved(isDark ? "dark" : "light");
  }, []);

  useEffect(() => {
    const saved = (localStorage.getItem(KEY) as Theme) || "system";
    setThemeState(saved);
    apply(saved);

    // Sistem tercihi degisirse ve kullanici "system" sectiyse takip et
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if ((localStorage.getItem(KEY) as Theme) === "system") apply("system");
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [apply]);

  function setTheme(t: Theme) {
    localStorage.setItem(KEY, t);
    setThemeState(t);
    apply(t);
  }

  return <Ctx.Provider value={{ theme, resolved, setTheme }}>{children}</Ctx.Provider>;
}
