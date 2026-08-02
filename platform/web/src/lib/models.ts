/**
 * Model catalogue.
 *
 * A curated list per provider so the user picks rather than types. Free text was
 * a trap: a single typo in a model id only surfaces as a provider error in the
 * middle of a review, after tokens have already been spent.
 *
 * ------------------------------------------------------------------------------
 * MAINTENANCE
 * ------------------------------------------------------------------------------
 * Model ids move faster than release cycles, so two escape hatches exist:
 *
 *   1. Every provider carries `allowsCustomModel`. Selecting "Custom…" reveals a
 *      text input, so a model released after this file was written is never a
 *      blocker.
 *   2. From phase 2 the OpenRouter list can be refreshed live from
 *      `GET /api/v1/models`, at which point this array becomes the offline
 *      fallback rather than the source of truth.
 *
 * `recommended` marks a sensible default for code review specifically: strong
 * reasoning over long diffs, not the cheapest or the largest context.
 */

import type { ProviderId } from "@/lib/api";

export interface ModelOption {
  /** The exact id sent to the provider. */
  id: string;
  label: string;
  /** Shown as secondary text — context window, tier, or a short note. */
  note?: string;
  recommended?: boolean;
}

export interface ProviderCatalogue {
  id: ProviderId;
  label: string;
  /** False until the adapter ships, so the UI can say so honestly. */
  adapterReady: boolean;
  /** Whether a hand-typed id is accepted. */
  allowsCustomModel: boolean;
  models: ModelOption[];
}

/** Sentinel for the "type your own" option. Not a real model id. */
export const CUSTOM_MODEL = "__custom__";

export const PROVIDER_CATALOGUE: ProviderCatalogue[] = [
  // -------------------------------------------------------------------------
  // API providers
  // -------------------------------------------------------------------------
  {
    id: "openrouter",
    label: "OpenRouter",
    adapterReady: true,
    allowsCustomModel: true,
    models: [
      {
        id: "anthropic/claude-sonnet-5",
        label: "Claude Sonnet 5",
        note: "strong on long diffs",
        recommended: true,
      },
      { id: "anthropic/claude-opus-5", label: "Claude Opus 5", note: "highest quality" },
      { id: "anthropic/claude-haiku-4.5", label: "Claude Haiku 4.5", note: "fast and cheap" },
      { id: "openai/gpt-5.6-sol", label: "GPT-5.6 Sol", note: "frontier coding" },
      { id: "openai/gpt-5.6-terra", label: "GPT-5.6 Terra", note: "balanced" },
      { id: "google/gemini-3.1-pro-preview", label: "Gemini 3.1 Pro", note: "large context" },
      { id: "google/gemini-3.6-flash", label: "Gemini 3.6 Flash", note: "fast" },
      { id: "deepseek/deepseek-v3.2", label: "DeepSeek V3.2", note: "open weights" },
      { id: "qwen/qwen3-coder-480b", label: "Qwen3 Coder 480B", note: "code specialist" },
      { id: "moonshotai/kimi-k2", label: "Kimi K2" },
      { id: "z-ai/glm-4.6", label: "GLM 4.6" },
    ],
  },
  {
    id: "anthropic",
    label: "Anthropic",
    adapterReady: true,
    allowsCustomModel: true,
    models: [
      {
        id: "claude-sonnet-5",
        label: "Claude Sonnet 5",
        note: "balanced",
        recommended: true,
      },
      { id: "claude-opus-5", label: "Claude Opus 5", note: "highest quality" },
      { id: "claude-fable-5", label: "Claude Fable 5", note: "fast and capable" },
      { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5", note: "lowest cost" },
    ],
  },
  {
    id: "openai",
    label: "OpenAI",
    adapterReady: true,
    allowsCustomModel: true,
    models: [
      { id: "gpt-5.6-terra", label: "GPT-5.6 Terra", note: "balanced", recommended: true },
      { id: "gpt-5.6-sol", label: "GPT-5.6 Sol", note: "frontier coding" },
      { id: "gpt-5.6-luna", label: "GPT-5.6 Luna", note: "fastest" },
    ],
  },
  {
    id: "gemini",
    label: "Google Gemini",
    adapterReady: true,
    allowsCustomModel: true,
    models: [
      {
        id: "gemini-3.1-pro-preview",
        label: "Gemini 3.1 Pro Preview",
        note: "very large context",
        recommended: true,
      },
      { id: "gemini-3.6-flash", label: "Gemini 3.6 Flash", note: "fast" },
      { id: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash Lite", note: "cheapest" },
    ],
  },
  {
    id: "ollama",
    label: "Ollama (local)",
    adapterReady: true,
    // Ollama models are whatever the user has pulled, so a fixed list would be
    // wrong more often than right.
    allowsCustomModel: true,
    models: [
      { id: "qwen3-coder:30b", label: "Qwen3 Coder 30B", recommended: true },
      { id: "deepseek-coder-v2:16b", label: "DeepSeek Coder V2 16B" },
      { id: "codellama:34b", label: "Code Llama 34B" },
      { id: "llama3.3:70b", label: "Llama 3.3 70B" },
    ],
  },

  // -------------------------------------------------------------------------
  // Local CLI agents
  // -------------------------------------------------------------------------
  {
    id: "claude_code",
    label: "Claude Code",
    adapterReady: true,
    allowsCustomModel: true,
    models: [
      { id: "sonnet", label: "Sonnet", note: "the CLI default", recommended: true },
      { id: "opus", label: "Opus" },
      { id: "haiku", label: "Haiku" },
    ],
  },
  {
    id: "copilot_cli",
    label: "GitHub Copilot CLI",
    adapterReady: true,
    allowsCustomModel: true,
    models: [
      { id: "auto", label: "Auto", note: "let Copilot choose", recommended: true },
      { id: "gpt-5.3-codex", label: "GPT-5.3 Codex" },
      { id: "claude-sonnet-4.6", label: "Claude Sonnet 4.6" },
      { id: "gpt-5.4", label: "GPT-5.4" },
    ],
  },
  {
    id: "kiro_cli",
    label: "Kiro CLI",
    adapterReady: true,
    allowsCustomModel: false,
    models: [
      {
        id: "kiro-default",
        label: "Configured Kiro model",
        note: "managed by Kiro CLI settings",
        recommended: true,
      },
    ],
  },
];

export function catalogueFor(providerId: ProviderId): ProviderCatalogue | undefined {
  return PROVIDER_CATALOGUE.find((provider) => provider.id === providerId);
}

/** Providers offered for a given execution mode. */
export function providersForMode(mode: "api" | "cli"): ProviderCatalogue[] {
  const cliProviders: ProviderId[] = ["claude_code", "copilot_cli", "kiro_cli"];
  return PROVIDER_CATALOGUE.filter((provider) =>
    mode === "cli"
      ? cliProviders.includes(provider.id)
      : !cliProviders.includes(provider.id),
  );
}

/** The recommended model for a provider, falling back to its first entry. */
export function defaultModelFor(providerId: ProviderId): string {
  const catalogue = catalogueFor(providerId);
  if (!catalogue) return "";
  return (
    catalogue.models.find((model) => model.recommended)?.id ??
    catalogue.models[0]?.id ??
    ""
  );
}

/** True when `modelId` is not in the provider's list — i.e. a custom entry. */
export function isCustomModel(providerId: ProviderId, modelId: string): boolean {
  const catalogue = catalogueFor(providerId);
  if (!catalogue) return true;
  return !catalogue.models.some((model) => model.id === modelId);
}

export function labelForProvider(providerId: ProviderId): string {
  return catalogueFor(providerId)?.label ?? providerId;
}
