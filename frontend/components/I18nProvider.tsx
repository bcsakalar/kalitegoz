"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { translate, type Lang } from "@/lib/i18n";

interface I18nCtx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const Ctx = createContext<I18nCtx>({ lang: "tr", setLang: () => {}, t: (k) => k });
export const useI18n = () => useContext(Ctx);
/** Kisayol: const t = useT(); t("nav.calls") */
export const useT = () => useContext(Ctx).t;

const KEY = "kg_lang";

export default function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("tr");

  useEffect(() => {
    const saved = localStorage.getItem(KEY) as Lang | null;
    if (saved === "tr" || saved === "en") {
      setLangState(saved);
      document.documentElement.lang = saved;
      return;
    }
    // Kayit yoksa tarayici dilinden tahmin et (TR degilse EN)
    const guess: Lang = navigator.language?.toLowerCase().startsWith("tr") ? "tr" : "en";
    setLangState(guess);
    document.documentElement.lang = guess;
  }, []);

  const setLang = useCallback((l: Lang) => {
    localStorage.setItem(KEY, l);
    setLangState(l);
    document.documentElement.lang = l;
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => translate(lang, key, vars),
    [lang],
  );

  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}
