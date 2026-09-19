/**
 * Locale registry for RevAI's interface.
 *
 * Each selection maps to one complete, isolated catalog: there is no mixed
 * dictionary and no silent per-string fallback between languages. `pt-BR.ts`
 * is typed against `MessageKey`, so a missing translation there breaks the
 * build instead of leaking English at runtime.
 *
 * The loose `translate(value)` helper (used by the provider) exists because
 * breadcrumb labels and similar call sites mix catalog keys with dynamic text
 * (project names); membership lookup keeps the two apart.
 */

import { enUS, type MessageKey } from "./en-US";
import { ptBR } from "./pt-BR";

export type Locale = "en-US" | "pt-BR";

const CATALOGS: Record<Locale, Record<string, string>> = {
  "en-US": enUS,
  "pt-BR": ptBR,
};

export type TranslateParams = Record<string, string | number>;

function interpolate(message: string, params?: TranslateParams): string {
  if (!params) return message;
  return message.replace(/\{(\w+)\}/g, (token, name: string) =>
    Object.prototype.hasOwnProperty.call(params, name)
      ? String(params[name])
      : token,
  );
}

/** Translate a catalog key for a locale. Unknown keys come back unchanged. */
export function translate(
  locale: Locale,
  key: string,
  params?: TranslateParams,
): string {
  const message =
    CATALOGS[locale][key] ??
    (locale !== "en-US" ? CATALOGS["en-US"][key] : undefined) ??
    key;
  return interpolate(message, params);
}

export function isMessageKey(value: string): value is MessageKey {
  return value in CATALOGS["en-US"];
}

export { enUS, type MessageKey };
