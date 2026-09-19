/**
 * Settings › Prompts.
 *
 * Two editable units with different save semantics:
 *
 * - **Default prompts** behave like the Engine form: one local draft, one
 *   atomic save, the shared auto-save preference honoured.
 * - **Scenarios** are a collection, so each card owns its draft and saves
 *   itself with its own PUT — a half-applied scenario list would be worse than
 *   an explicitly unsaved card.
 *
 * Both units edit only the instruction text. The anti-injection guard and the
 * JSON payload sentinel are fixed server-side scaffolding, so no edit here can
 * weaken the prompt-injection boundary — which is why the fields carry no
 * warning about "breaking the format".
 */

"use client";

import { useCallback, useMemo, useState } from "react";

import { SaveBar } from "@/components/save-bar";
import { useUiText } from "@/components/ui-preference-bootstrap";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, TextInput } from "@/components/ui/field";
import {
  ApiError,
  api,
  type ConfigResponse,
  type PromptDefaults,
  type PromptScenario,
  type PromptsResponse,
} from "@/lib/api";
import { useAutoSave } from "@/lib/use-auto-save";

type Status = "idle" | "saving" | "saved" | "error";

interface PromptsFormProps {
  initial: PromptsResponse;
  config: ConfigResponse["config"];
}

export function PromptsForm({ initial, config }: PromptsFormProps) {
  const { t } = useUiText();
  const locale = initial.locale;
  const [saved, setSaved] = useState<PromptDefaults>(initial.defaults);
  const [draft, setDraft] = useState<PromptDefaults>(initial.defaults);
  const [scenarios, setScenarios] = useState<PromptScenario[]>(initial.scenarios);
  const [configState, setConfigState] = useState(config);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);

  const dirty =
    draft.system_prompt !== saved.system_prompt || draft.user_prompt !== saved.user_prompt;

  const save = useCallback(async () => {
    setStatus("saving");
    setError(null);
    try {
      const response = await api.savePromptDefaults({
        locale,
        system_prompt: draft.system_prompt,
        user_prompt: draft.user_prompt,
      });
      setSaved(response);
      setDraft(response);
      setStatus("saved");
    } catch (cause) {
      setError(promptsError(cause, t));
      setStatus("error");
    }
  }, [draft, locale, t]);

  useAutoSave(configState, dirty, status === "saving", () => void save());

  async function decideAutoSave(value: boolean) {
    try {
      const response = await api.saveConfig({
        ...configState,
        ui: { ...configState.ui, auto_save: value },
      });
      setConfigState(response.config);
    } catch (cause) {
      setError(promptsError(cause, t));
      setStatus("error");
    }
  }

  function discard() {
    setDraft(saved);
    setStatus("idle");
    setError(null);
  }

  function restoreField(field: "system_prompt" | "user_prompt") {
    setDraft((current) => ({ ...current, [field]: initial.builtin[field] }));
    setStatus("idle");
  }

  async function createScenario(name: string) {
    setStatus("saving");
    setError(null);
    try {
      // Omitted prompts: the server copies the effective defaults of this locale.
      const scenario = await api.createPromptScenario({ name });
      setScenarios((current) => [...current, scenario]);
      setStatus("idle");
    } catch (cause) {
      setError(promptsError(cause, t));
      setStatus("error");
    }
  }

  const replaceScenario = useCallback((updated: PromptScenario) => {
    setScenarios((current) => current.map((s) => (s.id === updated.id ? updated : s)));
  }, []);

  const removeScenario = useCallback((scenarioId: string) => {
    setScenarios((current) => current.filter((s) => s.id !== scenarioId));
  }, []);

  return (
    <>
      {/* ---------------- default prompts ---------------- */}
      <Card className="mb-3.5">
        <CardHeader
          title={t("prompts.defaults.title")}
          icon={PROMPT_ICON}
          aside={saved.customized ? t("prompts.customized") : t("prompts.builtin")}
        />
        <CardBody>
          <p className="mb-4 text-[12.5px] leading-relaxed text-ink-muted">
            {t("prompts.defaultsIntro")}
          </p>

          <PromptTextArea
            id="default-system-prompt"
            label={t("prompts.systemPrompt")}
            hint={t("prompts.systemPromptHint")}
            value={draft.system_prompt}
            onChange={(value) => {
              setDraft((current) => ({ ...current, system_prompt: value }));
              setStatus("idle");
            }}
            onRestore={() => restoreField("system_prompt")}
            restoreLabel={t("prompts.restoreBuiltin")}
          />
          <PromptTextArea
            id="default-user-prompt"
            label={t("prompts.userPrompt")}
            hint={t("prompts.userPromptHint")}
            value={draft.user_prompt}
            onChange={(value) => {
              setDraft((current) => ({ ...current, user_prompt: value }));
              setStatus("idle");
            }}
            onRestore={() => restoreField("user_prompt")}
            restoreLabel={t("prompts.restoreBuiltin")}
          />

          <div className="mt-4 flex items-center gap-2.5 border-t border-line pt-3.5">
            <Button variant="ghost" onClick={() => setConfirmReset(true)}>
              {t("prompts.resetDefaults")}
            </Button>
          </div>
        </CardBody>
      </Card>

      <SaveBar
        dirty={dirty}
        status={status}
        summary={t("prompts.unsavedDefaults")}
        error={error}
        autoSave={configState.ui.auto_save}
        onSetAutoSave={decideAutoSave}
        onSave={() => void save()}
        onDiscard={discard}
      />

      {/* ---------------- scenarios ---------------- */}
      <Card className="mb-3.5">
        <CardHeader
          title={t("prompts.scenarios.title")}
          icon={SCENARIO_ICON}
          aside={t("prompts.scenarios.count", { count: scenarios.length })}
        />
        <CardBody>
          <p className="mb-4 text-[12.5px] leading-relaxed text-ink-muted">
            {t("prompts.scenariosIntro")}
          </p>

          <CreateScenario onCreate={createScenario} busy={status === "saving"} />

          {scenarios.length > 0 && (
            <div className="mt-4 flex flex-col gap-3.5">
              {scenarios.map((scenario) => (
                <ScenarioCard
                  key={scenario.id}
                  scenario={scenario}
                  onSaved={replaceScenario}
                  onDeleted={removeScenario}
                />
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {confirmReset && (
        <ConfirmDialog
          title={t("prompts.resetDialog.title")}
          body={t("prompts.resetDialog.body")}
          confirmLabel={t("prompts.resetDialog.confirm")}
          onCancel={() => setConfirmReset(false)}
          onConfirm={async () => {
            setConfirmReset(false);
            setStatus("saving");
            setError(null);
            try {
              const response = await api.resetPromptDefaults(locale);
              setSaved(response);
              setDraft(response);
              setStatus("saved");
            } catch (cause) {
              setError(promptsError(cause, t));
              setStatus("error");
            }
          }}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Scenario card
// ---------------------------------------------------------------------------

function ScenarioCard({
  scenario,
  onSaved,
  onDeleted,
}: {
  scenario: PromptScenario;
  onSaved: (updated: PromptScenario) => void;
  onDeleted: (scenarioId: string) => void;
}) {
  const { t } = useUiText();
  const [draft, setDraft] = useState<PromptScenario>(scenario);
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const dirty = useMemo(
    () =>
      draft.name !== scenario.name ||
      draft.system_prompt !== scenario.system_prompt ||
      draft.user_prompt !== scenario.user_prompt,
    [draft, scenario],
  );

  async function save() {
    setState("saving");
    setError(null);
    try {
      const updated = await api.updatePromptScenario(scenario.id, {
        name: draft.name,
        system_prompt: draft.system_prompt,
        user_prompt: draft.user_prompt,
      });
      onSaved(updated);
      setDraft(updated);
      setState("idle");
    } catch (cause) {
      setError(promptsError(cause, t));
      setState("error");
    }
  }

  async function remove() {
    setState("saving");
    setError(null);
    try {
      await api.deletePromptScenario(scenario.id);
      onDeleted(scenario.id);
    } catch (cause) {
      setError(promptsError(cause, t));
      setState("idle");
    }
  }

  return (
    <div className="rounded-control border border-line bg-canvas">
      <div className="flex items-center gap-2.5 border-b border-line px-3.5 py-2.5">
        <span className="truncate text-[12.5px] font-semibold">{scenario.name}</span>
        <Button
          variant="danger"
          className="ml-auto px-3 py-1.5 text-[12px]"
          onClick={() => setConfirmDelete(true)}
          disabled={state === "saving"}
        >
          {t("prompts.scenarios.delete")}
        </Button>
      </div>

      <div className="px-3.5 py-3">
        <Field label={t("prompts.scenarios.name")} htmlFor={`${scenario.id}-name`}>
          <TextInput
            id={`${scenario.id}-name`}
            value={draft.name}
            onChange={(event) => setDraft({ ...draft, name: event.target.value })}
          />
        </Field>
        <PromptTextArea
          id={`${scenario.id}-system`}
          label={t("prompts.systemPrompt")}
          value={draft.system_prompt}
          onChange={(value) => setDraft({ ...draft, system_prompt: value })}
        />
        <PromptTextArea
          id={`${scenario.id}-user`}
          label={t("prompts.userPrompt")}
          value={draft.user_prompt}
          onChange={(value) => setDraft({ ...draft, user_prompt: value })}
        />

        {error && (
          <p className="mt-2 rounded-control border border-critical-line bg-critical-surface px-3 py-2 text-[12px] text-critical">
            {error}
          </p>
        )}

        <div className="mt-3 flex justify-end gap-2.5">
          {dirty && (
            <Button variant="ghost" onClick={() => setDraft(scenario)} disabled={state === "saving"}>
              {t("save.discard")}
            </Button>
          )}
          <Button
            variant="primary"
            onClick={() => void save()}
            disabled={!dirty || state === "saving" || !draft.name.trim()}
          >
            {state === "saving" ? t("save.saving") : t("save.saveChanges")}
          </Button>
        </div>
      </div>

      {confirmDelete && (
        <ConfirmDialog
          title={t("prompts.deleteDialog.title", { name: scenario.name })}
          body={t("prompts.deleteDialog.body")}
          confirmLabel={t("prompts.scenarios.delete")}
          destructive
          onCancel={() => setConfirmDelete(false)}
          onConfirm={async () => {
            setConfirmDelete(false);
            await remove();
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create row
// ---------------------------------------------------------------------------

function CreateScenario({
  onCreate,
  busy,
}: {
  onCreate: (name: string) => Promise<void>;
  busy: boolean;
}) {
  const { t } = useUiText();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  async function submit() {
    if (!name.trim()) return;
    setCreating(true);
    await onCreate(name.trim());
    setName("");
    setCreating(false);
  }

  return (
    <div className="mb-4 flex items-end gap-2.5 border-b border-line pb-4">
      <div className="min-w-0 flex-1">
        <Field label={t("prompts.scenarios.newName")} htmlFor="new-scenario-name">
          <TextInput
            id="new-scenario-name"
            placeholder={t("prompts.scenarios.namePlaceholder")}
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && name.trim()) void submit();
            }}
          />
        </Field>
      </div>
      <Button
        variant="primary"
        onClick={() => void submit()}
        disabled={busy || creating || !name.trim()}
      >
        {creating || busy ? t("prompts.scenarios.creating") : t("prompts.scenarios.create")}
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared pieces
// ---------------------------------------------------------------------------

function PromptTextArea({
  id,
  label,
  hint,
  note,
  value,
  onChange,
  onRestore,
  restoreLabel,
}: {
  id: string;
  label: string;
  hint?: string;
  note?: string;
  value: string;
  onChange: (value: string) => void;
  onRestore?: () => void;
  restoreLabel?: string;
}) {
  return (
    <Field label={label} htmlFor={id} note={note} hint={hint}>
      <textarea
        id={id}
        rows={5}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full resize-y rounded-control border border-line-strong bg-paper px-3 py-2.5 font-mono text-[12.5px] leading-relaxed text-ink outline-none transition-shadow placeholder:text-ink-subtle focus:border-ink focus:shadow-[0_0_0_3px_var(--color-ring)]"
      />
      {onRestore && restoreLabel && (
        <button
          type="button"
          onClick={onRestore}
          className="mt-1.5 text-[11px] font-medium text-ink-subtle underline-offset-2 transition-colors hover:text-ink hover:underline"
        >
          {restoreLabel}
        </button>
      )}
    </Field>
  );
}

function ConfirmDialog({
  title,
  body,
  confirmLabel,
  destructive = false,
  onCancel,
  onConfirm,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  destructive?: boolean;
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
}) {
  const { t } = useUiText();
  return (
    <div role="presentation" className="fixed inset-0 z-50 grid place-items-center bg-black/25 p-4">
      <section
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-[420px] border border-line bg-paper shadow-2xl"
      >
        <div className="border-b border-line px-5 py-4">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-muted">{body}</p>
        </div>
        <div className="flex justify-end gap-2 border-t border-line px-5 py-4">
          <Button variant="ghost" onClick={onCancel}>
            {t("common.cancel")}
          </Button>
          <Button
            variant={destructive ? "danger" : "primary"}
            onClick={() => void onConfirm()}
          >
            {confirmLabel}
          </Button>
        </div>
      </section>
    </div>
  );
}

/** Map the backend's structured error keys onto translated messages. */
function promptsError(cause: unknown, t: (key: string, params?: Record<string, string | number>) => string): string {
  if (cause instanceof ApiError) {
    const key = ERROR_MESSAGE_KEYS[cause.message];
    if (key) return t(key);
  }
  return t("prompts.error.generic");
}

const ERROR_MESSAGE_KEYS: Record<string, string> = {
  "prompt_scenario.not_found": "prompts.error.notFound",
  "prompt_scenario.duplicate_name": "prompts.error.duplicateName",
};

// --- icons -----------------------------------------------------------------

const PROMPT_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px]">
    <path d="M4 7V5h16v2M12 5v14m-3 0h6" />
  </svg>
);

const SCENARIO_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px]">
    <rect x="3" y="4" width="18" height="14" rx="2" />
    <path d="M8 21h8M12 18v3" />
  </svg>
);
