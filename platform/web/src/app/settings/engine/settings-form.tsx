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
import { useUiText } from "@/components/ui-preference-bootstrap";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardRow } from "@/components/ui/card";
import { Field, Select, TextInput } from "@/components/ui/field";
import { NumberControl } from "@/components/ui/number-control";
import { Switch } from "@/components/ui/switch";
import { SonarLocalPanel } from "./sonar-local-panel";
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
import { useAutoSave } from "@/lib/use-auto-save";

/** Restored when a limit is switched from unlimited back to bounded. */
const DEFAULT_SPEND = 0.5;
const DEFAULT_CONTEXT = 60_000;

/** Deterministic analysers, with the tool each one shells out to. */
const ANALYSERS: { key: keyof AnalyzerConfig; labelKey: string; detailKey: string }[] = [
  { key: "security", labelKey: "engine.analyser.builtinSecurity", detailKey: "engine.analyser.builtinSecurityDetail" },
  { key: "semgrep", labelKey: "engine.analyser.semgrep", detailKey: "engine.analyser.semgrepDetail" },
  { key: "ruff", labelKey: "engine.analyser.ruff", detailKey: "engine.analyser.ruffDetail" },
  { key: "eslint", labelKey: "engine.analyser.eslint", detailKey: "engine.analyser.eslintDetail" },
  { key: "gitleaks", labelKey: "engine.analyser.gitleaks", detailKey: "engine.analyser.gitleaksDetail" },
  { key: "treesitter", labelKey: "engine.analyser.treesitter", detailKey: "engine.analyser.treesitterDetail" },
  { key: "checkstyle", labelKey: "engine.analyser.checkstyle", detailKey: "engine.analyser.checkstyleDetail" },
  { key: "project_tests", labelKey: "engine.analyser.projectTests", detailKey: "engine.analyser.projectTestsDetail" },
  { key: "project_build", labelKey: "engine.analyser.projectBuild", detailKey: "engine.analyser.projectBuildDetail" },
];

const BEHAVIOUR: { key: keyof AnalyzerConfig; labelKey: string; hintKey: string }[] = [
  {
    key: "skip_noise",
    labelKey: "engine.behaviour.skip_noise",
    hintKey: "engine.behaviour.skip_noise_hint",
  },
  {
    key: "changed_lines_only",
    labelKey: "engine.behaviour.changed_lines_only",
    hintKey: "engine.behaviour.changed_lines_only_hint",
  },
  {
    key: "dedupe_across_sources",
    labelKey: "engine.behaviour.dedupe_across_sources",
    hintKey: "engine.behaviour.dedupe_across_sources_hint",
  },
];

/** Map a model-catalogue note to its message key. Unknown notes pass through. */
const MODEL_NOTE_KEYS: Record<string, string> = {
  "strong on long diffs": "models.note.longDiffs",
  "highest quality": "models.note.highestQuality",
  "fast and cheap": "models.note.fastAndCheap",
  "frontier coding": "models.note.frontierCoding",
  balanced: "models.note.balanced",
  "large context": "models.note.largeContext",
  "very large context": "models.note.veryLargeContext",
  fast: "models.note.fast",
  "open weights": "models.note.openWeights",
  "code specialist": "models.note.codeSpecialist",
  "fast and capable": "models.note.fastAndCapable",
  "lowest cost": "models.note.lowestCost",
  fastest: "models.note.fastest",
  cheapest: "models.note.cheapest",
  "the CLI default": "models.note.cliDefault",
  "let Copilot choose": "models.note.letCopilotChoose",
  "fast and cost-efficient": "models.note.fastAndCostEfficient",
  "stronger reasoning": "models.note.strongerReasoning",
  Auto: "models.note.auto",
};

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
  const { t } = useUiText();
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

  async function saveDocument(document: RevaiConfig) {
    setStatus("saving");
    setError(null);
    try {
      const response = await api.saveConfig(document);
      setSaved(response.config);
      setDraft(response.config);
      // Re-derive from what the server actually stored, so the select reflects
      // reality rather than what we asked for.
      setCustomModel(
        isCustomModel(response.config.engine.provider_id, response.config.engine.model),
      );
      setStatus("saved");
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t("save.couldNotSave"));
      setStatus("error");
    }
  }

  function save() {
    void saveDocument(draft);
  }

  /**
   * Answer the auto-save offer. The decision travels with the current draft, so
   * answering also commits whatever the user had already changed — which is
   * what "yes, save automatically" means anyway.
   */
  function decideAutoSave(value: boolean) {
    const next = structuredClone(draft);
    next.ui.auto_save = value;
    void saveDocument(next);
  }

  useAutoSave(saved, dirty, status === "saving", save);

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
      setKeyError(cause instanceof ApiError ? cause.message : t("engine.couldNotStoreKey"));
      setKeyStatus("error");
    }
  }

  async function removeKey(providerId: ProviderId) {
    try {
      await api.deleteCredential(providerId);
      setCredentials((current) => current.filter((c) => c.provider_id !== providerId));
    } catch (cause) {
      setKeyError(cause instanceof ApiError ? cause.message : t("engine.couldNotRemoveKey"));
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
        <CardHeader title={t("engine.executionMode")} icon={BOLT} />
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

          <Field label={t("engine.provider")} htmlFor="provider">
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
                  {provider.adapterReady ? "" : t("engine.adapterLater")}
                </option>
              ))}
            </Select>
          </Field>

          {/* Model is a list, not free text: a typo in a model id only surfaces as
              a provider error mid-review, after tokens have been spent. */}
          <Field
            label={t("engine.model")}
            htmlFor="model"
            note={t("engine.offlineSuggestions", { count: catalogue?.models.length ?? 0 })}
            hint={
              isKiroCli
                ? t("engine.modelHint.kiro")
                : usingCustomModel
                ? t("engine.modelHint.custom")
                : t("engine.modelHint.catalogue")
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
                  {model.recommended ? t("engine.recommended") : ""}
                  {model.note && !model.recommended ? ` — ${t(MODEL_NOTE_KEYS[model.note] ?? model.note)}` : ""}
                </option>
              ))}
              {catalogue?.allowsCustomModel && (
                <option value={CUSTOM_MODEL}>{t("engine.customModel")}</option>
              )}
            </Select>

            {usingCustomModel && (
              <TextInput
                aria-label={t("engine.customModelAria")}
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
              label={t("engine.baseUrl")}
              htmlFor="base-url"
              note={t("engine.optional")}
              hint={t("engine.baseUrlHint")}
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
            title={requiresApiKey ? t("engine.apiKey") : t("engine.storedApiKeys")}
            icon={LOCK}
            aside={credentialsPath.split(/[\\/]/).pop()}
          />
          <CardBody>
            {requiresApiKey && (
              <Field
                label={t("engine.keyFor", { provider: labelForProvider(draft.engine.provider_id) })}
                htmlFor="api-key"
                note={t("engine.keyStoredNote")}
                hint={
                  <>
                    {t("engine.keyHint.before")} <code className="text-[11px]">{credentialsPath}</code>
                    {t("engine.keyHint.after")}
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
                    {keyStatus === "saving" ? t("engine.storing") : t("engine.store")}
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
                <p className="eyebrow mb-2.5">{t("engine.storedKeys")}</p>
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
                      {t("engine.remove")}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* ---------------- detection ----------------
          Only for the CLI mode. In API mode the cards above already name the
          provider, ask for its key and offer a base URL, so a status panel of
          every provider on the machine reads as noise; CLI mode is where the
          user actually picks between installed agents. */}
      {draft.engine.mode === "cli" && (
        <ProviderPanel activeProviderId={draft.engine.provider_id} />
      )}

      {/* ---------------- budget ---------------- */}
      <Card className="mb-3.5">
        <CardHeader title={t("engine.budgetCard")} icon={COIN} aside={t("engine.budgetHardStops")} />
        <CardBody>
          <div className="grid gap-3.5 sm:grid-cols-2">
            <Field
              label={t("engine.maxSpend")}
              htmlFor="max-spend"
              note={spendUnlimited ? t("engine.noLimit") : t("engine.abortsWhenExceeded")}
            >
              <NumberControl
                id="max-spend"
                min={0.01}
                step={0.05}
                prefix="$"
                suffix="USD"
                disabled={spendUnlimited}
                value={draft.budget.max_spend_usd}
                placeholder={spendUnlimited ? t("engine.unlimitedPlaceholder") : undefined}
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

            <Field label={t("engine.warnAbove")} htmlFor="warn-above" note={t("engine.asksConfirmation")}>
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
              label={t("engine.contextBudget")}
              htmlFor="context"
              note={contextUnlimited ? t("engine.noLimit") : t("engine.tokensSent")}
            >
              <NumberControl
                id="context"
                min={1000}
                step={1000}
                suffix={t("engine.unit.tokens")}
                disabled={contextUnlimited}
                value={draft.budget.max_context_tokens}
                placeholder={contextUnlimited ? t("engine.unlimitedPlaceholder") : undefined}
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
              label={t("engine.requestTimeout")}
              htmlFor="timeout"
              note={t("engine.seconds")}
              hint={t("engine.timeoutHint")}
            >
              <NumberControl
                id="timeout"
                min={1}
                step={30}
                suffix={t("engine.unit.sec")}
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
              label={t("engine.concurrentReviews")}
              htmlFor="concurrent-reviews"
              note={t("engine.localQueue")}
              hint={t("engine.queueHint")}
            >
              <NumberControl
                id="concurrent-reviews"
                min={1}
                step={1}
                suffix={t("engine.unit.runs")}
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
              label={t("engine.retryFailures")}
              htmlFor="retry-attempts"
              note={t("engine.sameProvider")}
              hint={t("engine.retryHint")}
            >
              <NumberControl
                id="retry-attempts"
                min={0}
                step={1}
                suffix={t("engine.unit.retries")}
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
                    ? t("engine.warn.both")
                    : spendUnlimited
                      ? t("engine.warn.spend")
                      : t("engine.warn.context")}
                </p>
                <p className="text-[12px] leading-relaxed text-ink-muted">
                  {spendUnlimited
                    ? t("engine.warn.spendBody")
                    : t("engine.warn.contextBody")}{" "}
                  {t("engine.warn.keepThreshold")}
                </p>
              </div>
            </div>
          )}

          {!spendUnlimited &&
            draft.budget.max_spend_usd !== null &&
            draft.budget.warn_above_usd > draft.budget.max_spend_usd && (
              <p className="mt-3 rounded-control border border-medium-line bg-medium-surface px-3 py-2 text-[12px] text-medium">
                {t("engine.warn.thresholdAboveCap")}
              </p>
            )}
        </CardBody>
      </Card>

      {/* ---------------- deterministic stage ---------------- */}
      <Card className="mb-3.5">
        <CardHeader title={t("engine.deterministicCard")} icon={CHECK_CIRCLE} aside="0 tokens" />
        <CardBody>
          <p className="mb-3.5 text-[12.5px] leading-relaxed text-ink-muted">
            {t("engine.deterministicIntro")}
          </p>

          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {ANALYSERS.map((analyser) => (
              <label
                key={analyser.key}
                className="flex cursor-pointer items-center gap-2.5 rounded-control border border-line bg-canvas px-3 py-2.5 transition-colors hover:bg-paper"
              >
                <Switch
                  label={t(analyser.labelKey)}
                  checked={Boolean(draft.analyzers[analyser.key])}
                  onChange={(checked) =>
                    patch((config) => {
                      (config.analyzers[analyser.key] as boolean) = checked;
                      return config;
                    })
                  }
                />
                <span className="min-w-0">
                  <b className="block text-[12.5px] font-medium">{t(analyser.labelKey)}</b>
                  <span className="numeric text-[10.5px] text-ink-subtle">
                    {t(analyser.detailKey)}
                  </span>
                </span>
              </label>
            ))}
          </div>

          <div className="mt-4 rounded-control border border-line bg-canvas p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <b className="block text-[12.5px] font-medium">{t("engine.sonar.title")}</b>
                <span className="text-[10.5px] text-ink-subtle">
                  {t("engine.sonar.detail")}
                </span>
              </div>
              <Switch
                label={t("engine.sonar.enable")}
                checked={draft.analyzers.sonarqube.enabled}
                onChange={(checked) => patch((config) => {
                  config.analyzers.sonarqube.enabled = checked;
                  return config;
                })}
              />
            </div>
            {draft.analyzers.sonarqube.enabled && (
              <div className="mt-3">
                <SonarLocalPanel
                  wsl={draft.analyzers.sonarqube.wsl}
                  onWslChange={(checked) => patch((config) => {
                    config.analyzers.sonarqube.wsl = checked;
                    return config;
                  })}
                />
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <Field label={t("engine.sonar.serverUrl")} htmlFor="sonarqube-server-url">
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
                <Field label={t("engine.sonar.projectKey")} htmlFor="sonarqube-project-key">
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
                <Field label={t("engine.sonar.scanner")} htmlFor="sonarqube-scanner">
                  <select
                    id="sonarqube-scanner"
                    value={draft.analyzers.sonarqube.scanner}
                    onChange={(event) => patch((config) => {
                      config.analyzers.sonarqube.scanner = event.target.value as SonarQubeConfig["scanner"];
                      return config;
                    })}
                    className="h-9 w-full rounded-control border border-line-strong bg-paper px-2.5 text-[11.5px] outline-none focus:border-ink"
                  >
                    <option value="auto">{t("engine.sonar.scanner.auto")}</option>
                    <option value="maven">{t("engine.sonar.scanner.maven")}</option>
                    <option value="gradle">{t("engine.sonar.scanner.gradle")}</option>
                    <option value="cli">{t("engine.sonar.scanner.cli")}</option>
                  </select>
                </Field>
                <div className="flex items-center gap-5 sm:col-span-2">
                  <Switch
                    label={t("engine.sonar.newCodeOnly")}
                    checked={draft.analyzers.sonarqube.new_code_only}
                    onChange={(checked) => patch((config) => {
                      config.analyzers.sonarqube.new_code_only = checked;
                      return config;
                    })}
                  />
                  <Switch
                    label={t("engine.sonar.qualityGate")}
                    checked={draft.analyzers.sonarqube.wait_for_quality_gate}
                    onChange={(checked) => patch((config) => {
                      config.analyzers.sonarqube.wait_for_quality_gate = checked;
                      return config;
                    })}
                  />
                </div>
                </div>
              </div>
            )}
          </div>

          <div className="mt-4 border-t border-line pt-1">
            {BEHAVIOUR.map((item) => (
              <CardRow key={item.key} label={t(item.labelKey)} hint={t(item.hintKey)}>
                <Switch
                  label={t(item.labelKey)}
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
  const { t } = useUiText();
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
      {t("engine.unlimited")}
      {checked && (
        <span className="font-semibold text-critical">{t("engine.noCapEnforced")}</span>
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
