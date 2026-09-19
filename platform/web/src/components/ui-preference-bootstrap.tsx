"use client";

import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { api, type UiConfig } from "@/lib/api";
import { translate, type Locale, type TranslateParams } from "@/lib/i18n";

type Translator = (key: string, params?: TranslateParams) => string;

const UiLocaleContext = createContext<{ locale: Locale; t: Translator }>({
  locale: "en-US",
  t: (key, params) => translate("en-US", key, params),
});

export function UiPreferenceProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>("en-US");
  useEffect(() => {
    const apply = (config: UiConfig) => {
      document.documentElement.dataset.theme = config.theme;
      document.documentElement.lang = config.locale;
      setLocale(config.locale);
    };
    void api.getConfig().then(({ config }) => apply(config.ui)).catch(() => undefined);
    const changed = (event: Event) => apply((event as CustomEvent<UiConfig>).detail);
    window.addEventListener("revai:ui-preferences", changed);
    return () => window.removeEventListener("revai:ui-preferences", changed);
  }, []);
  const value = useMemo(
    () => ({
      locale,
      t: (key: string, params?: TranslateParams) => translate(locale, key, params),
    }),
    [locale],
  );
  return <UiLocaleContext.Provider value={value}>{children}</UiLocaleContext.Provider>;
}

export function useUiText() {
  return useContext(UiLocaleContext);
}
