# RevAI Platform — Architecture Plan

> **Status:** ✅ **approved** — 2026-07-27. Implementation started at phase 0.
> **Scope:** everything lives under `platform/`. The existing `prompts/` and `revai/`
> (PowerShell) stay untouched and keep working in parallel.
>
> **Approved decisions:** phase 0 delivered first and reviewed before going deeper ·
> **OpenRouter is the first provider** (Anthropic, OpenAI and Gemini follow in phase 10) ·
> `platform/api` + `platform/web` as two independent folders.

---

## 1. Product decisions locked in

| Decision | Choice |
|---|---|
| Execution | Local, on the host. No container required to run. |
| Persistence | **YAML files** under `~/.revai/` — no MongoDB for now |
| Auth | None. Single user, `127.0.0.1` only |
| Engine | **BYOK model API (primary)** + **local CLI agent (alternative)** |
| Analysis | **Hybrid** — deterministic first, AI only on what survives |
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui |
| Design system | **Mock 03 "Paper Light"** |
| Git posting | Out of scope. Export only: JSON / Markdown / HTML |
| Language | English UI, i18n-ready for PT-BR. Code and docs in English |
| Legacy | Preserved; used as the functional reference for the Python port |

---

## 2. Design system — "Paper Light"

The chosen base, with concepts grafted in from mocks 01, 04 and 07.

### 2.1 Tokens

Mock 03's palette becomes the shadcn/ui theme (Tailwind v4 `@theme`):

```css
--background:      #fafafa;   --paper:    #ffffff;
--foreground:      #09090b;   --muted-fg: #52525b;   --subtle-fg: #a1a1aa;
--border:          #e4e4e7;   --border-strong: #d4d4d8;
--primary:         #09090b;   /* near-black, not a colour */
--info:    #2563eb;  --info-bg:    #eff6ff;
--critical:#dc2626;  --critical-bg:#fef2f2;
--medium:  #d97706;  --medium-bg:  #fffbeb;
--low:     #2563eb;  --low-bg:     #eff6ff;
--success: #059669;  --success-bg: #ecfdf5;
--radius: 0.625rem;
```

Fonts: **Geist** (UI) + **Geist Mono** (code, paths, numbers) via `next/font`.

Rules carried over from the mock: hairline 1px borders, **no gradients, no blur,
no coloured drop-shadows**, generous whitespace, numbers always monospaced.

A dark and system-aware variant remap the same token names — no component changes.

### 2.2 Concepts imported from the other mocks

Each is **re-skinned into Paper Light**, never copied visually.

| From | Concept | Where it lands |
|---|---|---|
| 07 | `Model API` ⇄ `Local CLI agent` selector | Onboarding + Settings |
| 07 | **Detected providers** panel | Settings › Engine |
| 07 | **Save to config.yaml** action bar | Every settings page |
| 07 | **Export & data** section | Settings › Data |
| 04 | **Pipeline** (stage list with progress) | Review run page |
| 04 | **Event stream** (live log) | Review run page |
| 01 | **Fallback API key** | Settings › Engine |

The pipeline and event stream are the part that needs the most care: mock 04 was
dark and dense, and you disliked that. In Paper Light they become a **vertical
stepper on white** with hairline connectors, and the event stream a **quiet
monospaced list** with a coloured dot per level — same information, calm surface.

---

## 3. System topology

```
┌─────────────────────────────────────────────────────────────┐
│  Browser · http://127.0.0.1:3000                            │
│  Next.js (App Router, RSC) + Tailwind + shadcn/ui           │
└───────────────┬─────────────────────────────────────────────┘
                │  REST (JSON)  +  SSE (live events)
┌───────────────▼─────────────────────────────────────────────┐
│  FastAPI · http://127.0.0.1:8799                            │
│                                                              │
│   api/routes ──► services ──► pipeline ──► providers        │
│                      │            │                          │
│                      │            └──► analyzers (linters)  │
│                      ▼                                       │
│                 storage (YAML repositories)                  │
└───────────────┬──────────────────────┬──────────────────────┘
                │                      │
        ~/.revai/*.yaml        git repo (read-only)
                               local CLIs / model APIs
```

Single process. Reviews run as `asyncio` tasks inside the API, tracked by a job
registry. No broker, no worker, no database.

---

## 4. Backend

### 4.1 Stack

| Concern | Choice | Why |
|---|---|---|
| Framework | **FastAPI** + Uvicorn | async native, SSE, OpenAPI for free |
| Models | **Pydantic v2** | validation + YAML round-trip in one place |
| Settings | pydantic-settings | env override of every config key |
| YAML | **ruamel.yaml** | round-trip preserving comments and key order |
| Locking | filelock | safe concurrent writes |
| Git | subprocess + **unidiff** | port of the current `.ps1` behaviour |
| Tokens | tiktoken + provider counters | budgeting before spending |
| Aggregation | **pandas** | dedupe, rank, metrics |
| AST | tree-sitter | complexity, symbol boundaries for chunking |
| Tests | pytest + pytest-asyncio + hypothesis | mirrors the Pester property tests |

**Deliberately not using LangChain.** I verified it has no integration for these
CLIs, and wrapping a full agent CLI in `BaseChatModel` throws away its tool loop,
session handling and cost accounting. LangGraph is worth revisiting only if the
pipeline later needs branching or resumable multi-agent flows — today it is a
linear sequence, and plain `asyncio` is simpler and easier to debug.

### 4.2 Module layout

```
platform/api/
├── pyproject.toml
├── revai/
│   ├── main.py                 FastAPI app, CORS to localhost, lifespan
│   ├── config.py               Settings, ~/.revai resolution
│   ├── api/routes/             projects · reviews · providers · settings · events · export
│   ├── domain/                 models.py · enums.py   (single source of truth)
│   ├── storage/
│   │   ├── base.py             Repository[T] Protocol
│   │   ├── yaml_store.py       atomic write + filelock + ruamel
│   │   └── repositories.py     Project · Review · Config · Credentials
│   ├── providers/
│   │   ├── base.py             Provider Protocol
│   │   ├── api/                openrouter (first) · anthropic · openai · gemini · ollama
│   │   ├── cli/                claude_code · copilot · kiro
│   │   ├── detection.py        PATH probe + version + auth status
│   │   └── registry.py
│   ├── pipeline/
│   │   ├── base.py             Stage Protocol
│   │   ├── context.py          PipelineContext (carries state + emits events)
│   │   ├── runner.py           sequential execution, cancellation, error capture
│   │   └── stages/             collect · filter · parse · static · chunk · ai · merge · report
│   ├── analyzers/              semgrep · ruff · eslint · gitleaks · treesitter
│   ├── git/repo.py             diff, branches, authorship
│   ├── events/bus.py           in-memory pub/sub → SSE
│   └── export/                 json · markdown · html
└── tests/
```

Three boundaries are deliberate and worth defending:

**`storage/base.py`** — every read/write goes through a `Repository` Protocol.
Swapping YAML for MongoDB later means adding `mongo_store.py` and changing one
line in the DI container. Nothing above the storage layer knows what a file is.

**`providers/base.py`** — API and CLI providers implement the same Protocol, so
the pipeline never branches on provider type.

**`pipeline/base.py`** — stages are independent and composable, which is what
makes the hybrid strategy tunable per project.

### 4.3 Provider abstraction

```python
class Provider(Protocol):
    id: str
    kind: Literal["api", "cli"]

    async def health(self) -> ProviderHealth: ...
    async def analyze(self, req: AnalysisRequest) -> AsyncIterator[ProviderEvent]: ...
```

`ProviderEvent` is a discriminated union: `Started | Delta | Findings | Usage | Finished | Failed`.
The pipeline consumes the same stream regardless of source.

The three CLIs are **very unequal** in headless mode — this is the single biggest
implementation risk, so the adapters differ substantially:

| | Structured output | Auth check | Adapter strategy |
|---|---|---|---|
| **OpenRouter** *(first)* | JSON schema via `response_format` | `GET /api/v1/key` → credits + limits | OpenAI-compatible. **Primary path.** |
| **API providers** | JSON schema / tool calling | key present | Guaranteed shape. **Recommended path.** |
| **Claude Code** | `--output-format json` + `--json-schema`, full envelope with `session_id`, `total_cost_usd`, `usage` | `claude auth status` → JSON, exit 0/1 | Cleanest CLI. Parse envelope directly. |
| **Copilot CLI** | JSONL, **schema undocumented** | **no `whoami` at all** | Parse `-p -s` output through the repair layer; evaluate `--acp --stdio` (a specified protocol) as the robust path |
| **Kiro CLI** | **none — plain text** | `kiro-cli whoami --format json` | Schema injected into the prompt, output through the repair layer. Lowest fidelity; flagged in the UI. |

Consequences already designed for:

- A **`FindingExtractor`** with tolerant JSON parsing (fenced-block extraction,
  trailing-comma repair, per-item validation) so one malformed finding does not
  lose the whole batch.
- **Kiro has no timeout of its own** → every CLI call is wrapped in
  `asyncio.wait_for` with a configurable ceiling.
- **Copilot has no auth-status command** → health check falls back to a trivial
  probe call, and the UI says "unknown" rather than lying.
- Cost is **estimated** for CLI providers that do not report it, and clearly
  labelled as an estimate in the UI.

### 4.4 The hybrid pipeline

```
collect → filter → parse → static → chunk → ai → merge → report
```

| Stage | Does | Token cost |
|---|---|---|
| **collect** | `git diff base...head`, or file list, or full tree | 0 |
| **filter** | Drops lockfiles, generated, minified, vendored, binaries, snapshots | 0 |
| **parse** | `unidiff` → hunks; keeps only `+`/`-` lines, context kept for understanding only | 0 |
| **static** | semgrep · ruff · eslint · gitleaks · tree-sitter, in parallel, each optional and skipped gracefully when absent | **0** |
| **chunk** | Groups hunks by file and symbol, enforces the token budget, drops trivial hunks | 0 |
| **ai** | Calls the provider **with the linter findings as context**, so it corroborates instead of repeating | ← the only cost |
| **merge** | pandas: cross-source dedupe, confidence ranking, severity normalisation | 0 |
| **report** | Persists YAML, renders exports | 0 |

Two details that matter more than they look:

**Feeding linter findings into the AI prompt** is what actually reduces noise.
The model stops re-reporting what a linter already found and instead judges
whether it is real, which is exactly what CodeRabbit means by filtering false
positives from 40+ scanners.

**Ports of the current PowerShell behaviour** live here: `collect` reproduces
`diff-selected-branch.ps1` and `diff-current-branch.ps1`, and the "only analyse
`+`/`-` lines" rule from `code-review.prompt.md` becomes the `parse` stage —
enforced in code rather than requested in a prompt.

Two known bugs get fixed in the port: the base branch **`develop` is currently
hardcoded** (becomes per-project config with auto-detection), and PowerShell's
`>` redirection **writes UTF-16LE** (Python writes UTF-8 explicitly).

### 4.5 Persistence

```
~/.revai/
├── config.yaml              engine, budgets, analyzers, UI prefs
├── credentials.yaml         API keys · chmod 600 · never in the project folder
├── projects/<id>.yaml
├── reviews/<project>/<id>.yaml
├── rules/default.yaml · custom.yaml
└── cache/diffs/             disposable
```

Every write is **atomic**: serialise → temp file in the same directory →
`os.replace()`. A `filelock` guards concurrent access. A `schema_version` field
on each document enables migrations.

Why this beats MongoDB here: the files are readable, diffable, versionable and
require zero infrastructure — which is the whole point of a local single-user
tool. The repository abstraction keeps the door open.

### 4.6 Domain model

```python
class Finding(BaseModel):
    id: str
    severity: Literal["critical", "medium", "low"]
    category: Literal["security", "bug", "performance", "maintainability", "style"]
    title: str
    description: str
    rationale: str                    # markdown, the "why this matters" block
    file: str
    line_start: int
    line_end: int | None
    source: str                       # "ai" | "semgrep" | "ruff" | ...
    rule_id: str | None               # CWE-347, S1192, ...
    confidence: float                 # 0..1, drives ranking
    suggested_patch: str | None       # unified diff
    status: Literal["open", "fixed", "dismissed", "false_positive"]
```

Note `id`, `confidence`, `category`, `source` and `suggested_patch` — none exist
in today's JSON. Their absence is why the current template renders
**"Branch undefined"**, and why nothing can be deduplicated or ranked. The legacy
shape (`title`, `priority`, `description`, `copilotSummary`, `file`, `lines`)
remains importable and exportable for backward compatibility.

### 4.7 API surface

```
GET    /api/health
GET    /api/providers                  detected engines + status
POST   /api/providers/{id}/verify
GET    /api/config                     PUT to save → writes config.yaml
GET    /api/projects                   POST · GET/{id} · DELETE
POST   /api/projects/open-local        path validation + git detection
POST   /api/projects/clone             remote → local clone
GET    /api/projects/{id}/branches
GET    /api/projects/{id}/tree         tracked files at a Git ref
GET    /api/projects/{id}/diff         patch + line counts + token/cost estimate
POST   /api/reviews                    starts a run, returns immediately
GET    /api/reviews/{id}
POST   /api/reviews/{id}/abort
GET    /api/reviews/{id}/events        SSE: pipeline + event stream
PATCH  /api/reviews/{id}/findings/{fid}
POST   /api/reviews/{id}/findings/{fid}/fix      returns a patch, never writes
GET    /api/reviews/{id}/export?format=json|md|html
POST   /api/export/all                 full .zip
```

`/events` is the SSE endpoint feeding both the **Pipeline** stepper and the
**Event stream**, replayable from an offset so a page refresh does not lose history.

**RevAI never writes to your repository.** Fixes are returned as patches that you
review and apply explicitly — this preserves the safety posture of the current
`fix-review-items` prompt.

---

## 5. Frontend

```
platform/web/
├── app/
│   ├── onboarding/       provider mode · detection · auth · workspace
│   ├── projects/         list · open local · clone · create
│   ├── projects/[id]/    branches, scope, file tree, cost estimate
│   ├── reviews/[id]/     running (pipeline + event stream) → results
│   ├── insights/         metrics, history, technical debt
│   └── settings/         engine · rules · budget · appearance · data
├── components/ui/        shadcn/ui, themed to Paper Light
├── components/           pipeline · event-stream · finding-card · diff-viewer · provider-card
└── lib/                  api client (typed from OpenAPI) · sse · i18n
```

Notable pieces:

- **Types generated from the FastAPI OpenAPI schema** — the frontend cannot drift
  from the backend contract.
- **Diff viewer**: split and unified, from mock 05's layout but in Paper Light.
- **i18n**: `next-intl`, all strings in `messages/en.json` from day one so PT-BR is
  a translation file, not a refactor.
- The current 2,675-line HTML template becomes the **standalone HTML export** — one
  self-contained offline file, same as today. Its XSS exposure (everything goes
  through `innerHTML`) gets fixed with proper escaping during the port.

---

## 6. Phased delivery

Each phase ends in something runnable and testable.

| Phase | Delivers | Validation |
|---|---|---|
| **0 · Skeleton** | `platform/` scaffold, FastAPI + Next.js talking, Paper Light theme, `/health` | `npm run dev` + `uvicorn` render a themed page |
| **1 · Storage & config** | Pydantic models, YAML repositories, atomic writes, Settings › Engine, **Save to config.yaml** | pytest + hypothesis on the store; config survives a restart |
| **2 · Providers** | Detection, health, **OpenRouter adapter**, **Detected providers** panel, onboarding, fallback key | Real probe of `copilot` and `kiro` + a live OpenRouter call |
| **3 · Projects & git** | Open local, clone, branch list, diff preview, file tree, cost estimate | Run against `code-review-labs` itself |
| **4 · Deterministic pipeline** | collect → filter → parse → static → chunk, **zero tokens** | Findings from semgrep/ruff with no API call |
| **5 · AI stage** | Provider streaming, `FindingExtractor`, merge/dedupe, **Pipeline + Event stream** UI | End-to-end review on a real branch |
| **6 · Results** | Finding list, split diff, patch generation, apply-with-confirmation | Self-review of this repository |
| **7 · Export & insights** | JSON / Markdown / standalone HTML, **Export & data**, dashboard | Legacy JSON round-trips |
| **8 · CLI adapters** | claude · copilot · kiro, with their asymmetries handled | Each CLI exercised headless |
| **9 · Packaging** | `docker-compose.yml` (optional), `revai` CLI entrypoint, docs, CI | Fresh-machine install test |
| **10 · More providers** | Anthropic · OpenAI · Gemini native adapters, Ollama | Same review, four providers, compared |

Phases 0–7 are the product. **8, 9 and 10 are deliberately last** — the CLI adapters
are the least reliable surface, and **OpenRouter alone already reaches every model**
that phase 10 adds natively.

### Why OpenRouter first

One key, hundreds of models, and an **OpenAI-compatible** surface made OpenRouter the
smallest useful first integration. It also returns real cost per request (`usage`
including a credits figure), which feeds the budget guard without any price table to
maintain. Phase 10 keeps each native wire format isolated behind the same provider
protocol and shares only transport-safe parsing, health, retry, and redaction helpers.

---

## 7. Risks and how they are handled

| Risk | Mitigation |
|---|---|
| **Kiro emits no JSON** | Schema in the prompt + tolerant extractor; fidelity flagged in the UI |
| **Copilot JSONL undocumented** | Repair layer now; evaluate ACP (`--acp --stdio`) in phase 8 |
| **Copilot has no auth check** | Probe call fallback; report "unknown" honestly |
| **Kiro has no timeout** | `asyncio.wait_for` on every CLI call |
| **Linters not installed** | Each analyzer is optional and skipped with a visible note |
| **Runaway cost** | Pre-flight estimate, hard `max_spend_usd`, confirmation above a threshold |
| **YAML corruption** | Atomic writes, file locking, `schema_version` |
| **Windows ⇄ WSL paths** | `pathlib` throughout, normalised at the API boundary |
| **Growth beyond single-user** | Repository + Provider Protocols already isolate storage and engines |

---

## 8. Repository layout

Two independent folders, as approved — each with its own toolchain, so a Python
developer never needs Node installed to work on the API and vice versa.

```
platform/
├── api/     FastAPI · uv · pyproject.toml
├── web/     Next.js · npm · package.json
├── docs/    ARCHITECTURE.md · PHASE-0.md
└── mocks/   the design exploration (reference only)
```

Verified toolchain on this machine: Node **24.15.0**, npm **11.12.1**,
Python **3.12.10**, uv **0.10.5**. `pnpm` is absent, so **npm** is used for the web app.
