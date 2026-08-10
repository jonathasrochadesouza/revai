"use client";

import { useEffect } from "react";

import { api } from "@/lib/api";

/** Applies persisted UI preferences before a page becomes interactive. */
export function UiPreferenceBootstrap() {
  useEffect(() => {
    void api.getConfig().then(({ config }) => {
      document.documentElement.dataset.theme = config.ui.theme;
      document.documentElement.lang = config.ui.locale;
    }).catch(() => undefined);
  }, []);

  return null;
}
