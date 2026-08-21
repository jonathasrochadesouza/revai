"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { SaveBar } from "@/components/save-bar";
import { Card, CardBody, CardHeader, CardRow } from "@/components/ui/card";
import { Select } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";
import { ApiError, api, type ConfigResponse, type RevaiConfig } from "@/lib/api";

type Theme = "light" | "dark" | "system";

const THEMES: { id: Theme; label: string; detail: string; icon: typeof Sun }[] = [
  { id: "light", label: "Light", detail: "Paper Light", icon: Sun },
  { id: "dark", label: "Dark", detail: "Low-glare workspace", icon: Moon },
  { id: "system", label: "System", detail: "Follow your device", icon: Monitor },
];

export function AppearanceForm({ initial }: { initial: ConfigResponse }) {
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

  async function save() {
    setStatus("saving");
    setError(null);
    try {
      const response = await api.saveConfig(draft);
      setSaved(response.config);
      setDraft(response.config);
      setStatus("saved");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not save preferences.");
      setStatus("error");
    }
  }

  function discard() {
    setDraft(saved);
    setError(null);
    setStatus("idle");
  }

  return (
    <>
      <Card className="mb-3.5">
        <CardHeader title="Appearance" icon={<Sun className="size-[15px]" />} />
        <CardBody>
          <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Colour theme">
            {THEMES.map(({ id, label, detail, icon: Icon }) => {
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
                  <span className="block text-[12px] font-semibold">{label}</span>
                  <span className={`mt-0.5 block text-[10.5px] ${selected ? "text-zinc-300" : "text-ink-subtle"}`}>{detail}</span>
                </button>
              );
            })}
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-ink-subtle">
            Theme changes apply immediately and are saved in your local config file.
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Language & review behaviour" icon={<Monitor className="size-[15px]" />} />
        <CardBody>
          <label className="mb-4 block">
            <span className="mb-[7px] flex items-center gap-2 text-[12.5px] font-medium text-ink-muted">
              Display language <span className="text-[11px] text-ink-subtle">English and Brazilian Portuguese</span>
            </span>
            <Select
              value={draft.ui.locale}
              onChange={(event) => patch((config) => { config.ui.locale = event.target.value as RevaiConfig["ui"]["locale"]; })}
              aria-label="Display language"
            >
              <option value="en-US">English (United States)</option>
              <option value="pt-BR">Português (Brasil)</option>
            </Select>
            <span className="mt-[7px] block text-[11.5px] leading-relaxed text-ink-subtle">
              This setting changes the document language plus core navigation and review controls. Provider-specific and advanced technical labels remain in English.
            </span>
          </label>

          <div className="border-t border-line pt-1">
            <CardRow label="Confirm expensive reviews" hint="Show the estimate and ask before a review reaches your warning threshold.">
              <Switch
                label="Confirm expensive reviews"
                checked={draft.ui.confirm_expensive_reviews}
                onChange={(checked) => patch((config) => { config.ui.confirm_expensive_reviews = checked; })}
              />
            </CardRow>
          </div>
        </CardBody>
      </Card>

      <SaveBar
        dirty={changes > 0}
        status={status}
        summary={status === "saved" ? "config.yaml" : `${changes} unsaved ${changes === 1 ? "change" : "changes"}`}
        error={error}
        filename="config.yaml"
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
