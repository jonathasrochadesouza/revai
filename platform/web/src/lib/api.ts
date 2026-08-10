/**
 * Typed client for the RevAI API.
 *
 * Phase 0 keeps these types hand-written because the surface is two endpoints.
 * From phase 2 they are generated from the FastAPI OpenAPI schema, so the
 * frontend can never drift from the backend contract.
 */

const DEFAULT_BASE_URL = "http://127.0.0.1:8799";

const PUBLIC_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? DEFAULT_BASE_URL;

// A containerized Next.js server reaches the API by its Compose service name,
// while the hydrated browser still uses the loopback-published URL. Non-public
// environment variables are stripped from the client bundle by Next.js.
export const API_BASE_URL =
  typeof window === "undefined"
    ? (process.env.REVAI_API_INTERNAL_URL?.replace(/\/$/, "") ?? PUBLIC_BASE_URL)
    : PUBLIC_BASE_URL;

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
  max_concurrent_reviews: number;
  max_retry_attempts: number;
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
  locale: "en-US" | "pt-BR";
  theme: "light" | "dark" | "system";
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

// --- projects and Git (phase 3) -------------------------------------------

export interface Project {
  id: string;
  name: string;
  path: string;
  remote_url: string | null;
  base_branch: string;
  current_branch: string | null;
  branches: string[];
  languages: string[];
  archived: boolean;
  created_at: string;
  last_reviewed_at: string | null;
}

export interface ProjectsResponse {
  projects: Project[];
}

export interface FolderPickerResponse {
  path: string | null;
}

export interface ProjectTree {
  ref: string;
  files: string[];
}

export interface DiffFile {
  path: string;
  additions: number;
  deletions: number;
  binary: boolean;
}

export interface DiffPreview {
  base: string;
  head: string;
  files: DiffFile[];
  additions: number;
  deletions: number;
  estimated_tokens: number;
  estimated_cost_usd: number;
  patch: string;
  truncated: boolean;
}

// --- hybrid review pipeline (phases 4-5) ----------------------------------

export type Severity = "critical" | "medium" | "low";
export type FindingCategory =
  | "security"
  | "bug"
  | "performance"
  | "maintainability"
  | "style";
export type FindingSource =
  | "ai"
  | "semgrep"
  | "ruff"
  | "eslint"
  | "gitleaks"
  | "checkstyle"
  | "treesitter";

export interface Finding {
  id: string;
  severity: Severity;
  category: FindingCategory;
  title: string;
  description: string;
  rationale: string;
  file: string;
  line_start: number;
  line_end: number | null;
  source: FindingSource;
  rule_id: string | null;
  confidence: number;
  suggested_patch: string | null;
  status: "open" | "fixed" | "dismissed" | "false_positive";
}

export interface ReviewStats {
  files_analysed: number;
  files_skipped: number;
  hunks_total: number;
  hunks_sent_to_ai: number;
  chunks_prepared: number;
  estimated_context_tokens: number;
  tokens_input: number;
  tokens_output: number;
  tokens_cached: number;
  cost_usd: number;
  cost_is_estimated: boolean;
  duration_ms: number;
}

export interface Review {
  id: string;
  project_id: string;
  scope: "branch_diff" | "selected_files" | "whole_project";
  status: "queued" | "running" | "completed" | "failed" | "aborted";
  base_branch: string | null;
  head_branch: string | null;
  selected_files: string[];
  provider_id: ProviderId | null;
  model: string | null;
  findings: Finding[];
  stats: ReviewStats;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface PipelineStage {
  name: "collect" | "filter" | "parse" | "static" | "chunk" | "ai" | "merge";
  status: "completed" | "failed";
  duration_ms: number;
  detail: string | null;
}

export interface AnalyzerRun {
  name: string;
  status: "completed" | "unavailable" | "failed";
  findings: number;
  duration_ms: number;
  detail: string | null;
}

export interface ReviewChunk {
  file: string;
  symbol: string | null;
  line_start: number;
  line_end: number;
  estimated_tokens: number;
}

export interface DeterministicReview {
  review: Review;
  stages: PipelineStage[];
  analyzers: AnalyzerRun[];
  chunks: ReviewChunk[];
}

export type ReviewStreamEvent =
  | { type: "review_queued"; review_id: string }
  | { type: "review_started"; review_id: string }
  | ({ type: "stage" } & PipelineStage)
  | ({ type: "analyzer" } & AnalyzerRun)
  | { type: "provider"; model: string }
  | { type: "delta"; characters: number }
  | { type: "retry"; attempt: number; message: string }
  | {
      type: "usage";
      input_tokens: number;
      output_tokens: number;
      cached_tokens: number;
      cost_usd: number | null;
      is_estimated: boolean;
    }
  | { type: "completed"; result: DeterministicReview }
  | { type: "failed"; message: string };

export interface StreamReviewOptions {
  signal?: AbortSignal;
  onEvent?: (event: ReviewStreamEvent) => void;
}

async function streamReview(
  projectId: string,
  base: string,
  head: string,
  options: StreamReviewOptions = {},
): Promise<DeterministicReview> {
  const path = `/api/projects/${projectId}/reviews/stream`;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...json("POST", { base, head }),
    cache: "no-store",
    headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
    signal: options.signal,
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response, path, { method: "POST" }), response.status);
  }
  if (!response.body) {
    throw new ApiError("The review stream returned no response body.", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed: DeterministicReview | null = null;

  const consume = (block: string) => {
    const payload = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!payload) return;
    const event = JSON.parse(payload) as ReviewStreamEvent;
    options.onEvent?.(event);
    if (event.type === "completed") completed = event.result;
    if (event.type === "failed") throw new ApiError(event.message, response.status);
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    blocks.forEach(consume);
    if (done) break;
  }
  if (buffer.trim()) consume(buffer);
  if (!completed) throw new ApiError("The review stream ended before completion.", response.status);
  return completed;
}

export interface ReviewsResponse {
  reviews: Review[];
}

// --- export and insights (phase 7) ---------------------------------------

export type InsightRange = "7d" | "30d" | "90d" | "all";
export type ExportFormat = "json" | "md" | "html";

export interface InsightTotals {
  reviews: number;
  completed_reviews: number;
  findings: number;
  open_findings: number;
  open_critical: number;
  resolved_findings: number;
  false_positives: number;
  total_cost_usd: number;
  median_duration_ms: number;
}

export interface ReviewTrendPoint {
  review_id: string;
  project_id: string;
  project_name: string;
  created_at: string;
  critical: number;
  medium: number;
  low: number;
}

export interface ProjectInsight {
  project_id: string;
  name: string;
  languages: string[];
  reviews: number;
  open_critical: number;
  open_findings: number;
  health_score: number;
  health_change: number | null;
  last_reviewed_at: string | null;
}

export interface InsightsResponse {
  range: InsightRange;
  generated_at: string;
  totals: InsightTotals;
  categories: Record<FindingCategory, number>;
  statuses: Record<Finding["status"], number>;
  trend: ReviewTrendPoint[];
  projects: ProjectInsight[];
}

export interface DataSummary {
  data_dir: string;
  reviews_dir: string;
  projects: number;
  reviews: number;
  storage_bytes: number;
  credentials_included_in_archive: false;
}

export function reviewExportUrl(
  reviewId: string,
  format: ExportFormat,
  legacy = false,
): string {
  const query = new URLSearchParams({ format });
  if (legacy) query.set("legacy", "true");
  return `${API_BASE_URL}/api/reviews/${encodeURIComponent(reviewId)}/export?${query}`;
}

async function exportAllData(): Promise<Blob> {
  const path = "/api/export/all";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { Accept: "application/zip" },
  });
  if (!response.ok) {
    throw new ApiError(await describeFailure(response, path, { method: "POST" }), response.status);
  }
  return response.blob();
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

  getProjects: () => request<ProjectsResponse>("/api/projects"),
  getProject: (projectId: string) =>
    request<Project>(`/api/projects/${projectId}`),
  openProject: (path: string) =>
    request<Project>("/api/projects/open", json("POST", { path })),
  cloneProject: (remoteUrl: string, destinationPath: string) =>
    request<Project>(
      "/api/projects/clone",
      json("POST", {
        remote_url: remoteUrl,
        destination_path: destinationPath,
      }),
    ),
  pickProjectFolder: () =>
    request<FolderPickerResponse>("/api/projects/pick-folder", {
      method: "POST",
    }),
  getProjectTree: (projectId: string, ref = "HEAD") =>
    request<ProjectTree>(
      `/api/projects/${projectId}/tree?ref=${encodeURIComponent(ref)}`,
    ),
  getProjectDiff: (projectId: string, base: string, head: string) =>
    request<DiffPreview>(
      `/api/projects/${projectId}/diff?base=${encodeURIComponent(base)}&head=${encodeURIComponent(head)}`,
    ),
  runDeterministicReview: (projectId: string, base: string, head: string) =>
    request<DeterministicReview>(
      `/api/projects/${projectId}/reviews/deterministic`,
      json("POST", { base, head }),
    ),
  streamReview,
  getProjectReviews: (projectId: string) =>
    request<ReviewsResponse>(`/api/projects/${projectId}/reviews`),
  updateFindingStatus: (
    projectId: string,
    reviewId: string,
    findingId: string,
    status: Finding["status"],
  ) =>
    request<Review>(
      `/api/projects/${projectId}/reviews/${reviewId}/findings/${findingId}`,
      json("PATCH", { status }),
    ),
  getInsights: (range: InsightRange = "30d") =>
    request<InsightsResponse>(`/api/insights?range=${range}`),
  getDataSummary: () => request<DataSummary>("/api/data"),
  exportAllData,
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
