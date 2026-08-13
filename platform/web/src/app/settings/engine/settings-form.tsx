/**
 * Settings › Engine.
 *
 * The whole document is edited locally and saved in one atomic PUT, mirroring how
 * the backend writes the file: either the new configuration lands completely or
 * the previous one is untouched. No field-by-field autosave, because a half-applied
 * configuration is the one state that would be genuinely confusing.
 */

"use client";

import { useCallback, useMemo, useState } from "react";

import { ModeSelector } from "@/components/mode-selector";
import { ProviderPanel } from "@/components/provider-panel";
import { SaveBar } from "@/components/save-bar";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardRow } from "@/components/ui/card";
import { Field, Select, TextInput } from "@/components/ui/field";
import { NumberControl } from "@/components/ui/number-control";
import { Switch } from "@/components/ui/switch";
import {
  ApiError,
  api,
  type AnalyzerConfig,
  type ConfigResponse,
  type CredentialSummary,
  type ProviderId,
  type RevaiConfig,
  type SonarQubeConfig,
} from "@/lib/api";
import {
  catalogueFor,
  CUSTOM_MODEL,
  defaultModelFor,
  isCustomModel,
  labelForProvider,
  providersForMode,
} from "@/lib/models";

/** Restored when a limit is switched from unlimited back to bounded. */
const DEFAULT_SPEND = 0.5;
const DEFAULT_CONTEXT = 60_000;

/** Deterministic analysers, with the tool each one shells out to. */
const ANALYSERS: { key: keyof AnalyzerConfig; label: string; detail: string }[] = [
  { key: "security", label: "Built-in security", detail: "dangerous execution APIs" },
  { key: "semgrep", label: "Semgrep", detail: "security patterns" },
  { key: "ruff", label: "Ruff", detail: "python" },
  { key: "eslint", label: "ESLint", detail: "javascript / typescript" },
  { key: "gitleaks", label: "Gitleaks", detail: "leaked secrets" },
  { key: "treesitter", label: "tree-sitter", detail: "AST, built in" },
  { key: "checkstyle", label: "Checkstyle", detail: "java" },
  { key: "project_tests", label: "Project tests", detail: "configured per project" },
  { key: "project_build", label: "Project build", detail: "configured per project" },
];

const BEHAVIOUR: { key: keyof AnalyzerConfig; label: string; hint: string }[] = [
  {
    key: "skip_noise",
    label: "Skip noise automatically",
    hint: "Drops lockfiles, generated code, minified bundles, snapshots and binaries before anything else runs.",
  },
  {
    key: "changed_lines_only",
    label: "Only review changed lines",
    hint: "Context lines are sent for understanding but never reported as findings.",
  },
  {
    key: "dedupe_across_sources",
    label: "Merge duplicate findings",
    hint: "When a linter and the model report the same problem, keep the higher-confidence one and merge the explanation.",
  },
];

interface SettingsFormProps {
  initial: ConfigResponse;
  initialCredentials: CredentialSummary[];
  credentialsPath: string;
}

export function SettingsForm({
  initial,
  initialCredentials,
  credentialsPath,
}: SettingsFormProps) {
  const [saved, setSaved] = useState<RevaiConfig>(initial.config);
  const [draft, setDraft] = useState<RevaiConfig>(initial.config);
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const [credentials, setCredentials] = useState(initialCredentials);
  const [apiKey, setApiKey] = useState("");
  const [keyStatus, setKeyStatus] = useState<"idle" | "saving" | "error">("idle");
  const [keyError, setKeyError] = useState<string | null>(null);

  // Seeded from the saved config so a model id typed in a previous session — or
  // written directly into config.yaml — still shows the custom input on load.
  const [customModel, setCustomModel] = useState(() =>
    isCustomModel(initial.config.engine.provider_id, initial.config.engine.model),
  );

  // `updated_at` is stamped server-side, so comparing it would report a phantom
  // change on every load. Everything else is diffed structurally.
  const changes = useMemo(() => countChanges(saved, draft), [saved, draft]);
  const dirty = changes > 0;

  const patch = useCallback((update: (config: RevaiConfig) => RevaiConfig) => {
    setDraft((current) => update(structuredClone(current)));
    setStatus("idle");
  }, []);

  async function save() {
    setStatus("saving");
    setError(null);
    try {
      const response = await api.saveConfig(draft);
      setSaved(response.config);
      setDraft(response.config);
      // Re-derive from what the server actually stored, so the select reflects
      // reality rather than what we asked for.
      setCustomModel(
        isCustomModel(response.config.engine.provider_id, response.config.engine.model),
      );
      setStatus("saved");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Could not save");
      setStatus("error");
    }
  }

  function discard() {
    setDraft(saved);
    setStatus("idle");
    setError(null);
    // `customModel` is local state, not part of the document, so reverting the
    // draft alone would leave the select stuck on "Custom…" while the value under
    // it had already snapped back to a catalogue entry.
    setCustomModel(isCustomModel(saved.engine.provider_id, saved.engine.model));
  }

  async function storeKey() {
    if (!apiKey.trim()) return;
    setKeyStatus("saving");
    setKeyError(null);
    try {
      const response = await api.putCredential({
        provider_id: draft.engine.provider_id,
        api_key: apiKey.trim(),
      });
      setCredentials(response.credentials);
      setApiKey(""); // never keep a secret in component state longer than needed
      setKeyStatus("idle");
    } catch (cause) {
      setKeyError(cause instanceof ApiError ? cause.message : "Could not store the key");
      setKeyStatus("error");
    }
  }

  async function removeKey(providerId: ProviderId) {
    try {
      await api.deleteCredential(providerId);
      setCredentials((current) => current.filter((c) => c.provider_id !== providerId));
    } catch (cause) {
      setKeyError(cause instanceof ApiError ? cause.message : "Could not remove the key");
    }
  }

  const isApiMode = draft.engine.mode === "api";
  const requiresApiKey = isApiMode && draft.engine.provider_id !== "ollama";
  const activeCredential = credentials.find(
    (c) => c.provider_id === draft.engine.provider_id,
  );

  const providers = providersForMode(draft.engine.mode);
  const catalogue = catalogueFor(draft.engine.provider_id);
  const usingCustomModel = customModel;
  const isKiroCli = draft.engine.provider_id === "kiro_cli";

  const spendUnlimited = draft.budget.max_spend_usd === null;
  const contextUnlimited = draft.budget.max_context_tokens === null;

  return (
    <>
      {/* ---------------- engine ---------------- */}
      <Card className="mb-3.5">
        <CardHeader title="Execution mode" icon={BOLT} />
        <CardBody>
          <div className="mb-4">
            <ModeSelector
              value={draft.engine.mode}
              onChange={(mode) => {
                setCustomModel(false);
                patch((config) => {
                  config.engine.mode = mode;
                  // Keep provider and model consistent with the mode. Without this
                  // the form can end up asking for an API key for a CLI provider,
                  // or holding a model id the new provider does not recognise.
                  const next: ProviderId = mode === "api" ? "openrouter" : "copilot_cli";
                  config.engine.provider_id = next;
                  config.engine.model = defaultModelFor(next);
                  config.engine.base_url = null;
                  return config;
                });
              }}
            />
          </div>

          <Field label="Provider" htmlFor="provider">
            <Select
              id="provider"
              value={draft.engine.provider_id}
              onChange={(event) => {
                const next = event.target.value as ProviderId;
                setCustomModel(false);
                patch((config) => {
                  config.engine.provider_id = next;
                  // Model ids are provider-specific, so carrying the old one over
                  // would produce a request the new provider rejects.
                  config.engine.model = defaultModelFor(next);
                  config.engine.base_url = null;
                  return config;
                });
              }}
            >
              {providers.map((provider) => (
                <option key={provider.id} value={provider.id}>
                  {provider.label}
                  {provider.adapterReady ? "" : " — adapter arrives later"}
                </option>
              ))}
            </Select>
          </Field>

          {/* Model is a list, not free text: a typo in a model id only surfaces as
              a provider error mid-review, after tokens have been spent. */}
          <Field
            label="Model"
            htmlFor="model"
            note={`${catalogue?.models.length ?? 0} offline suggestions`}
            hint={
              isKiroCli
                ? "RevAI passes this exact model to Kiro CLI 2.18+ and runs an isolated, read-only agent with MCP and tools disabled."
                : usingCustomModel
                ? "Custom ids are passed through verbatim. Confirm the id in your provider dashboard before running a review."
                : "These are offline suggestions. Provider model catalogs change frequently; use Custom when your provider lists a newer id."
            }
          >
            <Select
              id="model"
              value={usingCustomModel ? CUSTOM_MODEL : draft.engine.model}
              onChange={(event) => {
                const chosen = event.target.value;
                if (chosen === CUSTOM_MODEL) {
                  setCustomModel(true);
                  return;
                }
                setCustomModel(false);
                patch((config) => {
                  config.engine.model = chosen;
                  return config;
                });
              }}
            >
              {catalogue?.models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.label}
                  {model.recommended ? " — recommended" : ""}
                  {model.note && !model.recommended ? ` — ${model.note}` : ""}
                </option>
              ))}
              {catalogue?.allowsCustomModel && (
                <option value={CUSTOM_MODEL}>Custom…</option>
              )}
            </Select>

            {usingCustomModel && (
              <TextInput
                aria-label="Custom model id"
                className="mt-2.5"
                placeholder="provider/model-id"
                value={draft.engine.model}
                onChange={(event) =>
                  patch((config) => {
                    config.engine.model = event.target.value;
                    return config;
                  })
                }
              />
            )}
          </Field>

          {isApiMode && (
            <Field
              label="Base URL"
              htmlFor="base-url"
              note="optional"
              hint="Override the selected provider endpoint for a proxy or self-hosted service."
            >
              <TextInput
                id="base-url"
                placeholder={defaultBaseUrlFor(draft.engine.provider_id)}
                value={draft.engine.base_url ?? ""}
                onChange={(event) =>
                  patch((config) => {
                    config.engine.base_url = event.target.value || null;
                    return config;
                  })
                }
              />
            </Field>
          )}
        </CardBody>
      </Card>

      {/* ---------------- credentials ---------------- */}
      {isApiMode && (requiresApiKey || credentials.length > 0) && (
        <Card className="mb-3.5">
          <CardHeader
            title={requiresApiKey ? "API key" : "Stored API keys"}
            icon={LOCK}
            aside={credentialsPath.split(/[\\/]/).pop()}
          />
          <CardBody>
            {requiresApiKey && (
              <Field
                label={`Key for ${labelForProvider(draft.engine.provider_id)}`}
                htmlFor="api-key"
                note="stored with chmod 600"
                hint={
                  <>
                    Written to <code className="text-[11px]">{credentialsPath}</code>,
                    never inside a project folder and never in git. The key is never
                    returned by the API once stored.
                  </>
                }
              >
                <div className="flex gap-2.5">
                  <TextInput
                    id="api-key"
                    type="password"
                    autoComplete="off"
                    placeholder={activeCredential ? activeCredential.masked_key : "sk-…"}
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                  />
                  <Button
                    onClick={storeKey}
                    disabled={!apiKey.trim() || keyStatus === "saving"}
                  >
                    {keyStatus === "saving" ? "Storing…" : "Store"}
                  </Button>
                </div>
              </Field>
            )}

            {keyError && (
              <p className="mt-2 rounded-control border border-critical-line bg-critical-surface px-3 py-2 text-[12px] text-critical">
                {keyError}
              </p>
            )}

            {credentials.length > 0 && (
              <div className="mt-4 border-t border-line pt-3.5">
                <p className="eyebrow mb-2.5">Stored keys</p>
                {credentials.map((credential) => (
                  <div
                    key={credential.provider_id}
                    className="flex items-center gap-3 border-b border-line py-2.5 last:border-b-0 last:pb-0"
                  >
                    <span className="text-[13px] font-medium">
                      {labelForProvider(credential.provider_id)}
                    </span>
                    <code className="numeric rounded-xs bg-canvas px-2 py-1 text-[11px] text-ink-muted">
                      {credential.masked_key}
                    </code>
                    <Button
                      variant="danger"
                      className="ml-auto px-3 py-1.5 text-[12px]"
                      onClick={() => removeKey(credential.provider_id)}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* ---------------- detection ----------------
          Placed after credentials because storing a key changes what this panel
          reports, so reading downwards matches the order things are done in. */}
      <ProviderPanel activeProviderId={draft.engine.provider_id} />

      {/* ---------------- budget ---------------- */}
      <Card className="mb-3.5">
        <CardHeader title="Budget & limits" icon={COIN} aside="hard stops" />
        <CardBody>
          <div className="grid gap-3.5 sm:grid-cols-2">
            <Field
              label="Max spend per review"
              htmlFor="max-spend"
              note={spendUnlimited ? "no limit" : "aborts when exceeded"}
            >
              <NumberControl
                id="max-spend"
                min={0.01}
                step={0.05}
                prefix="$"
                suffix="USD"
                disabled={spendUnlimited}
                value={draft.budget.max_spend_usd}
                placeholder={spendUnlimited ? "Unlimited" : undefined}
                onCommit={(next) =>
                  patch((config) => {
                    config.budget.max_spend_usd = next;
                    return config;
                  })
                }
              />
              <UnlimitedToggle
                id="spend-unlimited"
                checked={spendUnlimited}
                onChange={(checked) =>
                  patch((config) => {
                    config.budget.max_spend_usd = checked ? null : DEFAULT_SPEND;
                    // With no cap, a warning threshold can no longer exceed it.
                    return config;
                  })
                }
              />
            </Field>

            <Field label="Warn above" htmlFor="warn-above" note="asks for confirmation">
              <NumberControl
                id="warn-above"
                min={0}
                step={0.05}
                prefix="$"
                suffix="USD"
                value={draft.budget.warn_above_usd}
                onCommit={(next) =>
                  patch((config) => {
                    config.budget.warn_above_usd = next;
                    return config;
                  })
                }
              />
            </Field>

            <Field
              label="Context budget"
              htmlFor="context"
              note={contextUnlimited ? "no limit" : "tokens sent to the model"}
            >
              <NumberControl
                id="context"
                min={1000}
                step={1000}
                suffix="tokens"
                disabled={contextUnlimited}
                value={draft.budget.max_context_tokens}
                placeholder={contextUnlimited ? "Unlimited" : undefined}
                onCommit={(next) =>
                  patch((config) => {
                    config.budget.max_context_tokens = next;
                    return config;
                  })
                }
              />
              <UnlimitedToggle
                id="context-unlimited"
                checked={contextUnlimited}
                onChange={(checked) =>
                  patch((config) => {
                    config.budget.max_context_tokens = checked ? null : DEFAULT_CONTEXT;
                    return config;
                  })
                }
              />
            </Field>

            <Field
              label="Request timeout"
              htmlFor="timeout"
              note="seconds"
              hint="Kiro CLI has no timeout of its own, so RevAI enforces this one."
            >
              <NumberControl
                id="timeout"
                min={1}
                step={30}
                suffix="sec"
                value={draft.budget.request_timeout_s}
                onCommit={(next) =>
                  patch((config) => {
                    config.budget.request_timeout_s = next;
                    return config;
                  })
                }
              />
            </Field>

            <Field
              label="Concurrent reviews"
              htmlFor="concurrent-reviews"
              note="local queue"
              hint="Additional reviews wait safely until a running review releases a slot."
            >
              <NumberControl
                id="concurrent-reviews"
                min={1}
                step={1}
                suffix="runs"
                value={draft.budget.max_concurrent_reviews}
                onCommit={(next) =>
                  patch((config) => {
                    config.budget.max_concurrent_reviews = Math.round(next);
                    return config;
                  })
                }
              />
            </Field>

            <Field
              label="Retry transient failures"
              htmlFor="retry-attempts"
              note="same provider"
              hint="Retries timeouts, rate limits, and transport failures only. It never silently switches models."
            >
              <NumberControl
                id="retry-attempts"
                min={0}
                step={1}
                suffix="retries"
                value={draft.budget.max_retry_attempts}
                onCommit={(next) =>
                  patch((config) => {
                    config.budget.max_retry_attempts = Math.round(next);
                    return config;
                  })
                }
              />
            </Field>
          </div>

          {/* Unlimited is the one setting here that can cost real money, so it is
              called out rather than left as a quiet checkbox state. */}
          {(spendUnlimited || contextUnlimited) && (
            <div className="mt-3.5 flex gap-2.5 rounded-control border border-critical-line bg-critical-surface px-3.5 py-3">
              <span className="mt-px shrink-0 text-critical">{ALERT_TRIANGLE}</span>
              <div>
                <p className="mb-1 text-[12.5px] font-semibold text-critical">
                  {spendUnlimited && contextUnlimited
                    ? "Spend and context are both unlimited"
                    : spendUnlimited
                      ? "Spending is unlimited"
                      : "Context size is unlimited"}
                </p>
                <p className="text-[12px] leading-relaxed text-ink-muted">
                  {spendUnlimited
                    ? "A review will run to completion no matter what it costs. On a large repository with an expensive model this can be tens of dollars in a single run."
                    : "A single request may send the entire diff, which can exceed the model's context window and fail after you have already paid for the input."}{" "}
                  Keep the warning threshold set so you are still asked before an
                  expensive run starts.
                </p>
              </div>
            </div>
          )}

          {!spendUnlimited &&
            draft.budget.max_spend_usd !== null &&
            draft.budget.warn_above_usd > draft.budget.max_spend_usd && (
              <p className="mt-3 rounded-control border border-medium-line bg-medium-surface px-3 py-2 text-[12px] text-medium">
                The warning threshold is above the hard cap, so it could never fire. The
                backend will reject this.
              </p>
            )}
        </CardBody>
      </Card>

      {/* ---------------- deterministic stage ---------------- */}
      <Card className="mb-3.5">
        <CardHeader title="Deterministic stage" icon={CHECK_CIRCLE} aside="0 tokens" />
        <CardBody>
          <p className="mb-3.5 text-[12.5px] leading-relaxed text-ink-muted">
            These run before the model and cost no AI tokens. Results are merged by stable
            identity after analysis; unavailable tools are reported as degraded instead of
            silently appearing successful.
          </p>

          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {ANALYSERS.map((analyser) => (
              <label
                key={analyser.key}
                className="flex cursor-pointer items-center gap-2.5 rounded-control border border-line bg-canvas px-3 py-2.5 transition-colors hover:bg-paper"
              >
                <Switch
                  label={analyser.label}
                  checked={Boolean(draft.analyzers[analyser.key])}
                  onChange={(checked) =>
                    patch((config) => {
                      (config.analyzers[analyser.key] as boolean) = checked;
                      return config;
                    })
                  }
                />
                <span className="min-w-0">
                  <b className="block text-[12.5px] font-medium">{analyser.label}</b>
                  <span className="numeric text-[10.5px] text-ink-subtle">
                    {analyser.detail}
                  </span>
                </span>
              </label>
            ))}
          </div>

          <div className="mt-4 rounded-control border border-line bg-canvas p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <b className="block text-[12.5px] font-medium">SonarQube Server / Community Build</b>
                <span className="text-[10.5px] text-ink-subtle">
                  Build-tool-aware scan, Compute Engine wait, new-code issues and quality gate.
                </span>
              </div>
              <Switch
                label="Enable SonarQube"
                checked={draft.analyzers.sonarqube.enabled}
                onChange={(checked) => patch((config) => {
                  config.analyzers.sonarqube.enabled = checked;
                  return config;
                })}
              />
            </div>
            {draft.analyzers.sonarqube.enabled && (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <Field label="Server URL" htmlFor="sonarqube-server-url">
                  <input
                    id="sonarqube-server-url"
                    value={draft.analyzers.sonarqube.server_url}
                    onChange={(event) => patch((config) => {
                      config.analyzers.sonarqube.server_url = event.target.value;
                      return config;
                    })}
                    placeholder="http://127.0.0.1:9000"
                    className="h-9 w-full rounded-control border border-line-strong bg-paper px-2.5 font-mono text-[11.5px] outline-none focus:border-ink"
                  />
                </Field>
                <Field label="Project key" htmlFor="sonarqube-project-key">
                  <input
                    id="sonarqube-project-key"
                    value={draft.analyzers.sonarqube.project_key ?? ""}
                    onChange={(event) => patch((config) => {
                      config.analyzers.sonarqube.project_key = event.target.value || null;
                      return config;
                    })}
                    placeholder="company:project"
                    className="h-9 w-full rounded-control border border-line-strong bg-paper px-2.5 font-mono text-[11.5px] outline-none focus:border-ink"
                  />
                </Field>
                <Field label="Scanner" htmlFor="sonarqube-scanner">
                  <select
                    id="sonarqube-scanner"
                    value={draft.analyzers.sonarqube.scanner}
                    onChange={(event) => patch((config) => {
                      config.analyzers.sonarqube.scanner = event.target.value as SonarQubeConfig["scanner"];
                      return config;
                    })}
                    className="h-9 w-full rounded-control border border-line-strong bg-paper px-2.5 text-[11.5px] outline-none focus:border-ink"
                  >
                    <option value="auto">Auto — prefer Maven/Gradle</option>
                    <option value="maven">Maven</option>
                    <option value="gradle">Gradle</option>
                    <option value="cli">Generic CLI</option>
                  </select>
                </Field>
                <div className="flex items-center gap-5 sm:col-span-2">
                  <Switch
                    label="New-code issues only"
                    checked={draft.analyzers.sonarqube.new_code_only}
                    onChange={(checked) => patch((config) => {
                      config.analyzers.sonarqube.new_code_only = checked;
                      return config;
                    })}
                  />
                  <Switch
                    label="Require quality gate"
                    checked={draft.analyzers.sonarqube.wait_for_quality_gate}
                    onChange={(checked) => patch((config) => {
                      config.analyzers.sonarqube.wait_for_quality_gate = checked;
                      return config;
                    })}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="mt-4 border-t border-line pt-1">
            {BEHAVIOUR.map((item) => (
              <CardRow key={item.key} label={item.label} hint={item.hint}>
                <Switch
                  label={item.label}
                  checked={Boolean(draft.analyzers[item.key])}
                  onChange={(checked) =>
                    patch((config) => {
                      (config.analyzers[item.key] as boolean) = checked;
                      return config;
                    })
                  }
                />
              </CardRow>
            ))}
          </div>
        </CardBody>
      </Card>

      <SaveBar
        dirty={dirty}
        status={status}
        summary={
          status === "saved"
            ? "config.yaml"
            : `${changes} unsaved ${changes === 1 ? "change" : "changes"}`
        }
        error={error}
        filename="config.yaml"
        onSave={save}
        onDiscard={discard}
      />
    </>
  );
}

function defaultBaseUrlFor(providerId: ProviderId): string {
  const urls: Partial<Record<ProviderId, string>> = {
    openrouter: "https://openrouter.ai/api/v1",
    anthropic: "https://api.anthropic.com/v1",
    openai: "https://api.openai.com/v1",
    gemini: "https://generativelanguage.googleapis.com/v1beta",
    ollama: "http://127.0.0.1:11434",
  };
  return urls[providerId] ?? "";
}

/**
 * Count the fields that differ.
 *
 * `updated_at` and `schema_version` are excluded on purpose: the server owns both,
 * so comparing them would leave the form permanently dirty.
 *
 * The double cast through `unknown` is required because the section types are
 * closed interfaces with no index signature — TypeScript is right to object, and
 * narrowing it here keeps the assertion in one auditable place.
 */
function countChanges(saved: RevaiConfig, draft: RevaiConfig): number {
  const sections = ["engine", "budget", "analyzers", "ui"] as const;

  return sections.reduce((total, section) => {
    const before = saved[section] as unknown as Record<string, unknown>;
    const after = draft[section] as unknown as Record<string, unknown>;

    const changed = Object.keys(after).filter((key) => before[key] !== after[key]);
    return total + changed.length;
  }, 0);
}

/**
 * The "unlimited" escape hatch for a numeric limit.
 *
 * A checkbox rather than a magic value in the number field: typing `0` or clearing
 * the input to mean "no limit" is guesswork, and guesswork about a spend cap is
 * expensive. The label carries the risk so the choice is never accidental.
 */
function UnlimitedToggle({
  id,
  checked,
  onChange,
}: {
  id: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label
      htmlFor={id}
      className="mt-2 flex cursor-pointer items-center gap-2 text-[11.5px] text-ink-subtle transition-colors hover:text-ink-muted"
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-3.5 cursor-pointer accent-[var(--color-critical)]"
      />
      Unlimited
      {checked && (
        <span className="font-semibold text-critical">— no cap will be enforced</span>
      )}
    </label>
  );
}

// --- icons -----------------------------------------------------------------

const BOLT = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px]">
    <path d="M13 2 3 14h8l-1 8 10-12h-8l1-8z" />
  </svg>
);

const LOCK = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px]">
    <rect x="3" y="11" width="18" height="11" rx="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

const COIN = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px]">
    <circle cx="12" cy="12" r="9" />
    <path d="M15 9.4a3.5 3.5 0 0 0-6 2.6c0 3 6 2 6 5a3.5 3.5 0 0 1-6 2.6M12 6v12" />
  </svg>
);

const CHECK_CIRCLE = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px]">
    <path d="M22 11.1V12a10 10 0 1 1-5.9-9.1" />
    <polyline points="22 4 12 14 9 11" />
  </svg>
);

const ALERT_TRIANGLE = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-4">
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);
