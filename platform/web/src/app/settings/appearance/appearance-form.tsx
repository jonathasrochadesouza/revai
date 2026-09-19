"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";
import { useApiErrorText } from "@/lib/use-api-error-text";
import { SaveBar } from "@/components/save-bar";
import { Card, CardBody, CardHeader, CardRow } from "@/components/ui/card";
import { Select } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";
import { api, type ConfigResponse, type RevaiConfig } from "@/lib/api";
import { useAutoSave } from "@/lib/use-auto-save";

type Theme = "light" | "dark" | "system";

const THEMES: { id: Theme; labelKey: string; detailKey: string; icon: typeof Sun }[] = [
  { id: "light", labelKey: "settings.appearance.theme.light", detailKey: "settings.appearance.theme.lightDetail", icon: Sun },
  { id: "dark", labelKey: "settings.appearance.theme.dark", detailKey: "settings.appearance.theme.darkDetail", icon: Moon },
  { id: "system", labelKey: "settings.appearance.theme.system", detailKey: "settings.appearance.theme.systemDetail", icon: Monitor },
];

export function AppearanceForm({ initial }: { initial: ConfigResponse }) {
  const { t } = useUiText();
  const errorText = useApiErrorText();
  const [saved, setSaved] = useState(initial.config);
  const [draft, setDraft] = useState(initial.config);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const changes = useMemo(() => countChanges(saved, draft), [saved, draft]);

  // Side effects that reach outside this component (DOM attributes, the
  // cross-component preference event) must happen after commit, not inside
  // a setState updater or synchronously alongside another setState call.
  // Otherwise React can warn/error with "Cannot update a component while
  // rendering a different component" when UiPreferenceProvider reacts to
  // the dispatched event.
  useEffect(() => {
    applyPreferences(draft);
  }, [draft]);

  function patch(update: (config: RevaiConfig) => void) {
    setDraft((current) => {
      const next = structuredClone(current);
      update(next);
      return next;
    });
    setStatus("idle");
  }

  async function saveDocument(document: RevaiConfig) {
    setStatus("saving");
    setError(null);
    try {
      const response = await api.saveConfig(document);
      setSaved(response.config);
      setDraft(response.config);
      setStatus("saved");
    } catch (cause) {
      setError(errorText(cause));
      setStatus("error");
    }
  }

  function save() {
    void saveDocument(draft);
  }

  /** Answer the auto-save offer; the current edits travel with the decision. */
  function decideAutoSave(value: boolean) {
    const next = structuredClone(draft);
    next.ui.auto_save = value;
    void saveDocument(next);
  }

  useAutoSave(saved, changes > 0, status === "saving", save);

  function discard() {
    setDraft(saved);
    setError(null);
    setStatus("idle");
  }

  return (
    <>
      <Card className="mb-3.5">
        <CardHeader title={t("settings.appearance.cardTitle")} icon={<Sun className="size-[15px]" />} />
        <CardBody>
          <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label={t("settings.appearance.themeAria")}>
            {THEMES.map(({ id, labelKey, detailKey, icon: Icon }) => {
              const selected = draft.ui.theme === id;
              return (
                <button
                  key={id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => patch((config) => { config.ui.theme = id; })}
                  className={`rounded-control border p-3 text-left transition-colors ${selected ? "border-ink bg-ink text-paper" : "border-line-strong bg-paper text-ink hover:bg-canvas"}`}
                >
                  <Icon className="mb-5 size-4" strokeWidth={1.8} />
                  <span className="block text-[12px] font-semibold">{t(labelKey)}</span>
                  <span className={`mt-0.5 block text-[10.5px] ${selected ? "text-paper/75" : "text-ink-subtle"}`}>{t(detailKey)}</span>
                </button>
              );
            })}
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-ink-subtle">
            {t("settings.appearance.themeHint")}
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title={t("settings.appearance.languageCard")} icon={<Monitor className="size-[15px]" />} />
        <CardBody>
          <label className="mb-4 block">
            <span className="mb-[7px] flex items-center gap-2 text-[12.5px] font-medium text-ink-muted">
              {t("settings.appearance.displayLanguage")} <span className="text-[11px] text-ink-subtle">{t("settings.appearance.supportedLocales")}</span>
            </span>
            <Select
              value={draft.ui.locale}
              onChange={(event) => patch((config) => { config.ui.locale = event.target.value as RevaiConfig["ui"]["locale"]; })}
              aria-label={t("settings.appearance.displayLanguage")}
            >
              <option value="en-US">{t("settings.appearance.locale.enUS")}</option>
              <option value="pt-BR">{t("settings.appearance.locale.ptBR")}</option>
            </Select>
            <span className="mt-[7px] block text-[11.5px] leading-relaxed text-ink-subtle">
              {t("settings.appearance.localeHint")}
            </span>
          </label>

          <div className="border-t border-line pt-1">
            <CardRow label={t("settings.appearance.confirmExpensive")} hint={t("settings.appearance.confirmExpensiveHint")}>
              <Switch
                label={t("settings.appearance.confirmExpensive")}
                checked={draft.ui.confirm_expensive_reviews}
                onChange={(checked) => patch((config) => { config.ui.confirm_expensive_reviews = checked; })}
              />
            </CardRow>
            <CardRow label={t("save.autoSavePreference")} hint={t("save.autoSaveHint")}>
              <Switch
                label={t("save.autoSavePreference")}
                checked={draft.ui.auto_save === true}
                onChange={(checked) => patch((config) => { config.ui.auto_save = checked; })}
              />
            </CardRow>
          </div>
        </CardBody>
      </Card>

      <SaveBar
        dirty={changes > 0}
        status={status}
        summary={t(changes === 1 ? "common.unsavedOne" : "common.unsavedOther", { count: changes })}
        error={error}
        autoSave={saved.ui.auto_save}
        onSetAutoSave={decideAutoSave}
        onSave={save}
        onDiscard={discard}
      />
    </>
  );
}

function countChanges(saved: RevaiConfig, draft: RevaiConfig): number {
  return Object.entries(draft.ui).filter(([key, value]) => saved.ui[key as keyof typeof saved.ui] !== value).length;
}

function applyPreferences(config: RevaiConfig) {
  document.documentElement.dataset.theme = config.ui.theme;
  document.documentElement.lang = config.ui.locale;
  window.dispatchEvent(new CustomEvent("revai:ui-preferences", { detail: config.ui }));
}
