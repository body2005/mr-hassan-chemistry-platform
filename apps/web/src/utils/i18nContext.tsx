import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { ar, LocaleSchema } from "../locales/ar";
import { en } from "../locales/en";

export type Language = "ar" | "en";

interface I18nContextType {
  lang: Language;
  dir: "rtl" | "ltr";
  setLang: (l: Language) => void;
  toggleLang: () => void;
  t: (path: string, params?: Record<string, string | number>) => string;
  isAr: boolean;
  isEn: boolean;
}

const I18nContext = createContext<I18nContextType | null>(null);

const bundles: Record<Language, LocaleSchema> = { ar, en };

function getNestedValue(obj: unknown, path: string): string | undefined {
  const parts = path.split(".");
  let current: unknown = obj;
  for (const part of parts) {
    if (current && typeof current === "object" && part in (current as Record<string, unknown>)) {
      current = (current as Record<string, unknown>)[part];
    } else {
      return undefined;
    }
  }
  return typeof current === "string" ? current : undefined;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Language>(() => {
    try {
      const saved = localStorage.getItem("lms_lang");
      return (saved as Language) === "en" ? "en" : "ar";
    } catch {
      return "ar";
    }
  });

  const setLang = useCallback((newLang: Language) => {
    setLangState(newLang);
    try {
      localStorage.setItem("lms_lang", newLang);
    } catch {
      // Ignore storage errors
    }
  }, []);

  const toggleLang = useCallback(() => {
    setLang(lang === "ar" ? "en" : "ar");
  }, [lang, setLang]);

  useEffect(() => {
    const dir = lang === "ar" ? "rtl" : "ltr";
    document.documentElement.setAttribute("lang", lang);
    document.documentElement.setAttribute("dir", dir);
    try {
      localStorage.setItem("lms_lang", lang);
    } catch {
      // Ignore storage errors
    }
  }, [lang]);

  const t = useCallback(
    (path: string, params?: Record<string, string | number>): string => {
      const bundle = bundles[lang] || bundles.ar;
      let text = getNestedValue(bundle, path);
      if (text === undefined && lang !== "ar") {
        text = getNestedValue(bundles.ar, path);
      }
      if (text === undefined) {
        return path;
      }
      if (params) {
        return Object.entries(params).reduce((acc, [key, val]) => {
          return acc.replace(new RegExp(`\\{${key}\\}`, "g"), String(val));
        }, text);
      }
      return text;
    },
    [lang]
  );

  const value: I18nContextType = {
    lang,
    dir: lang === "ar" ? "rtl" : "ltr",
    setLang,
    toggleLang,
    t,
    isAr: lang === "ar",
    isEn: lang === "en",
  };

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useTranslation() {
  const context = useContext(I18nContext);
  if (!context) {
    // Fallback safe defaults if used outside provider
    const fallbackLang: Language = typeof localStorage !== "undefined" && localStorage.getItem("lms_lang") === "en" ? "en" : "ar";
    const fallbackBundle = bundles[fallbackLang] || bundles.ar;
    return {
      lang: fallbackLang,
      dir: fallbackLang === "ar" ? ("rtl" as const) : ("ltr" as const),
      setLang: () => {},
      toggleLang: () => {},
      t: (path: string, params?: Record<string, string | number>) => {
        const text = getNestedValue(fallbackBundle, path) || getNestedValue(bundles.ar, path) || path;
        if (params) {
          return Object.entries(params).reduce((acc, [key, val]) => {
            return acc.replace(new RegExp(`\\{${key}\\}`, "g"), String(val));
          }, text);
        }
        return text;
      },
      isAr: fallbackLang === "ar",
      isEn: fallbackLang === "en",
    };
  }
  return context;
}
