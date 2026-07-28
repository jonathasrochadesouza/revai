/**
 * Typed client for the RevAI API.
 *
 * Phase 0 keeps these types hand-written because the surface is two endpoints.
 * From phase 2 they are generated from the FastAPI OpenAPI schema, so the
 * frontend can never drift from the backend contract.
 */

const DEFAULT_BASE_URL = "http://127.0.0.1:8799";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? DEFAULT_BASE_URL;

// --- response shapes -------------------------------------------------------

export interface HealthResponse {
  status: "ok";
  app: string;
  version: string;
  environment: string;
}

export interface RuntimeInfo {
  python_version: string;
  platform: string;
  data_dir: string;
  data_dir_exists: boolean;
}

// --- configuration (phase 1) ----------------------------------------------

export type EngineMode = "api" | "cli";

export type ProviderId =
  | "openrouter"
  | "anthropic"
  | "openai"
  | "gemini"
  | "ollama"
  | "claude_code"
  | "copilot_cli"
  | "kiro_cli";

export interface EngineConfig {
  mode: EngineMode;
  provider_id: ProviderId;
  model: string;
  base_url: string | null;
}

export interface BudgetConfig {
  /** `null` means unlimited — see docs/PHASE-1.md. */
  max_spend_usd: number | null;
  /** `null` means unlimited. */
  max_context_tokens: number | null;
  warn_above_usd: number;
  request_timeout_s: number;
}

export interface AnalyzerConfig {
  semgrep: boolean;
  ruff: boolean;
  eslint: boolean;
  gitleaks: boolean;
  checkstyle: boolean;
  treesitter: boolean;
  skip_noise: boolean;
  changed_lines_only: boolean;
  dedupe_across_sources: boolean;
}

export interface UiConfig {
  locale: string;
  theme: string;
  confirm_expensive_reviews: boolean;
}

export interface RevaiConfig {
  schema_version: number;
  engine: EngineConfig;
  budget: BudgetConfig;
  analyzers: AnalyzerConfig;
  ui: UiConfig;
  updated_at: string;
}

export interface ConfigResponse {
  config: RevaiConfig;
  path: string;
  /** False before the first save — the UI shows defaults as unsaved. */
  exists: boolean;
}

/** A stored credential. The key itself is never transmitted. */
export interface CredentialSummary {
  provider_id: ProviderId;
  label: string | null;
  masked_key: string;
  created_at: string;
}

export interface CredentialsResponse {
  credentials: CredentialSummary[];
  path: string;
}

// --- provider detection (phase 2) ------------------------------------------

export type ProviderKind = "api" | "cli";

/**
 * How usable a provider is right now.
 *
 * `unknown` is not a placeholder: GitHub Copilot CLI ships no auth-status command
 * and returns exit code 0 even for invalid input, so its state genuinely cannot be
 * determined without spending a request. See docs/PHASE-2.md.
 */
export type HealthState = "ready" | "needs_auth" | "unknown" | "not_found" | "error";

export interface ProviderHealth {
  provider_id: ProviderId;
  kind: ProviderKind;
  state: HealthState;
  version: string | null;
  /** Absolute path of the resolved binary. CLI providers only. */
  executable: string | null;
  detail: string | null;
  /** The command that would fix it, shown verbatim. */
  remediation: string | null;
  /** False when RevAI recognises the provider but has not implemented it yet. */
  adapter_ready: boolean;
  checked_at: string;
}

export interface ProvidersResponse {
  providers: ProviderHealth[];
  active_provider_id: ProviderId;
  active_is_usable: boolean;
}

/** A provider is usable only if the adapter exists *and* the state allows it. */
export function isUsable(health: ProviderHealth): boolean {
  return health.adapter_ready && (health.state === "ready" || health.state === "unknown");
}

/** Raised for any non-2xx response, carrying the status for the caller. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Fetch a JSON endpoint.
 *
 * `cache: "no-store"` because every endpoint here reflects live local state —
 * caching a health check would defeat its purpose.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: { Accept: "application/json", ...init?.headers },
  });

  if (!response.ok) {
    // The backend returns FastAPI's `detail` for every error it raises. Surfacing
    // it verbatim matters because a malformed config.yaml produces a message that
    // names the offending field, and the user needs to see it.
    throw new ApiError(await describeFailure(response, path, init), response.status);
  }

  // 204 has no body; parsing it would throw.
  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function describeFailure(
  response: Response,
  path: string,
  init?: RequestInit,
): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      // Pydantic validation errors: [{ loc: [...], msg: "..." }, ...]
      return body.detail
        .map((item) => {
          const entry = item as { loc?: unknown[]; msg?: string };
          const where = (entry.loc ?? []).filter((p) => p !== "body").join(".");
          return where ? `${where}: ${entry.msg}` : (entry.msg ?? "invalid");
        })
        .join("; ");
    }
  } catch {
    // Fall through to the generic message below.
  }
  return `${init?.method ?? "GET"} ${path} failed with ${response.status}`;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  runtime: () => request<RuntimeInfo>("/api/runtime"),

  getConfig: () => request<ConfigResponse>("/api/config"),
  saveConfig: (config: RevaiConfig) =>
    request<ConfigResponse>("/api/config", json("PUT", config)),

  getCredentials: () => request<CredentialsResponse>("/api/credentials"),
  putCredential: (input: {
    provider_id: ProviderId;
    api_key: string;
    label?: string | null;
  }) => request<CredentialsResponse>("/api/credentials", json("PUT", input)),
  deleteCredential: (providerId: ProviderId) =>
    request<void>(`/api/credentials/${providerId}`, { method: "DELETE" }),

  /** Pass `kind` to list only CLI agents or only hosted APIs. */
  getProviders: (kind?: ProviderKind) =>
    request<ProvidersResponse>(`/api/providers${kind ? `?kind=${kind}` : ""}`),
  verifyProvider: (providerId: ProviderId) =>
    request<ProviderHealth>(`/api/providers/${providerId}/verify`, { method: "POST" }),
};

/** Result of probing the backend, used to render the connection panel. */
export type ConnectionState =
  | { connected: true; health: HealthResponse; runtime: RuntimeInfo }
  | { connected: false; reason: string };

/**
 * Probe the backend without throwing.
 *
 * The landing page must still render when the API is down — that is precisely
 * when the user most needs to be told how to start it.
 */
export async function probeBackend(): Promise<ConnectionState> {
  try {
    const [health, runtime] = await Promise.all([api.health(), api.runtime()]);
    return { connected: true, health, runtime };
  } catch (error) {
    return {
      connected: false,
      reason: error instanceof Error ? error.message : "Unknown error",
    };
  }
}
