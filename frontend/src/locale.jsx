import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { detectLanguage, normalizeLang, t as translate } from "./i18n.js";

const STORAGE_KEY = "memoryvault.lang";
const LocaleContext = createContext(null);

function safeRead() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function safeWrite(value) {
  try {
    window.localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* storage disabled — language still works for this session */
  }
}

export function LocaleProvider({ children }) {
  const [lang, setLangState] = useState(() =>
    detectLanguage({
      search: typeof window === "undefined" ? "" : window.location.search,
      stored: typeof window === "undefined" ? "" : safeRead(),
      browser: typeof navigator === "undefined" ? "" : navigator.language,
    })
  );

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    safeWrite(lang);
  }, [lang]);

  const value = useMemo(
    () => ({
      lang,
      setLang: (next) => setLangState(normalizeLang(next) || "en"),
      t: (key, vars) => translate(lang, key, vars),
    }),
    [lang]
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useI18n must be used inside LocaleProvider");
  return ctx;
}
