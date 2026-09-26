## Context

RevAI's API (`platform/api`, FastAPI) currently lets FastAPI's default 422
shape leak straight to the browser, and every `HTTPException` uses a
hand-written English `detail` string — some of which forward raw `OSError`,
`YAMLError`, or git stderr text. The frontend (`platform/web`) has exactly one
place error text is assembled: `describeFailure()` in `lib/api.ts`, which joins
pydantic's `loc` and `msg` into the "budget: Value error, ..." style string
the user flagged. There is no error translation today, even though
`ui.locale` (`en-US` | `pt-BR`) already drives navigation-label translation via
`useUiText()`/`PT_BR` in `ui-preference-bootstrap.tsx`. There is also no toast
or notification primitive anywhere in the codebase — every screen renders its
own ad hoc inline red banner, and the settings pages show a bare "Preferences
unavailable" block when the API is unreachable.

This is the first OpenSpec change in this repository; there are no existing
`openspec/specs/` capabilities to reconcile against.

## Goals / Non-Goals

**Goals:**
- Every error the user can see has a stable, translatable identity
  (`error_key`) instead of hand-formatted prose, decided once on the backend
  and rendered twice (en-US, pt-BR) on the frontend.
- One backend choke point converts any raised error into the response
  contract — no route handler formats `detail` itself.
- One frontend catalog resolves `error_key` + `params` into a sentence — no
  component string-matches error text.
- A single reusable toast component replaces every ad hoc inline error banner
  outside the settings-save flow, with defined FIFO/capacity/timing/hover
  behavior.
- The settings "backend unreachable" fallback becomes a real recovery screen
  with a copyable, Docker-Compose-aware AI prompt.

**Non-Goals:**
- Not adding a third locale or generalizing to a pluggable i18n library (e.g.
  `next-intl`, ICU message format) — two hardcoded locales, same pattern as
  the existing `PT_BR` dictionary.
- Not versioning the API or keeping a compatibility shim for the old error
  shape. This ships as one atomic breaking change across both apps.
- Not adding retry/backoff logic to `describeFailure`/`request()` beyond what
  exists — this change is about message shape and presentation, not resilience.
- Not touching the `SaveBar` component's visual design (light, sticky, bottom
  bar) — only the text it renders becomes translated.
- Not changing which conditions raise which HTTP status codes — the mapping of
  "what fails and why" is untouched, only "what the client is told" changes.

## Decisions

### 1. Error response contract: `{ error_key, params }`

```json
{ "detail": { "error_key": "budget.warn_above_exceeds_max", "params": { "warn_above_usd": 1.4, "max_spend_usd": 0.25 } } }
```

- `error_key`: dot-namespaced, stable string (`<domain>.<reason>`), one per
  distinct user-facing situation. Domains mirror the module that raises them:
  `budget.*`, `project.*`, `review.*`, `git.*`, `storage.*`, `provider.*`,
  `credential.*`, `folder_picker.*`, `sonarqube.*`, `ai_pipeline.*`.
- `params`: a flat JSON object of raw values only (numbers, strings, paths) —
  never pre-formatted text, never HTML, never already-localized content. The
  frontend catalog owns all phrasing and number/currency formatting
  (`Intl.NumberFormat`, already used in `insights-dashboard.tsx`).
- Rejected alternative — keep `detail` as a string but namespace it
  (`"budget.warn_above_exceeds_max: warn $1.40 exceeds max $0.25"`): rejected
  because the frontend would have to re-parse a string to recover the
  interpolation values, which is exactly the fragility this change removes.
- Rejected alternative — full server-side localization (`Accept-Language`
  negotiation, backend renders the final string): rejected because `ui.locale`
  is a stored *application* preference read by the frontend, not an HTTP
  header, and duplicating the phrasing catalog in Python would mean maintaining
  two copies of every translation.

### 2. Backend: one exception type, one handler, `PydanticCustomError` for validators

- New `revai.errors` module: `class RevaiError(Exception)` carrying
  `error_key: str` and `params: dict[str, Any]`, plus a `status_code: int`.
  Every current `raise HTTPException(status_code=..., detail="...")` site
  becomes `raise RevaiError(status_code=..., error_key="...", params={...})`.
- A single `@app.exception_handler(RevaiError)` in `main.py` renders the
  contract's JSON body and status code. This is the only place that builds a
  `JSONResponse` for an application error.
- A second `@app.exception_handler(RequestValidationError)` overrides FastAPI's
  default 422 renderer. It walks `exc.errors()`; entries produced by
  `PydanticCustomError` already carry a `type` equal to the custom error's
  first constructor argument (its `error_key`) and `ctx` equal to `params` —
  the handler reads those directly instead of parsing `msg`. Entries from a
  plain built-in pydantic error (e.g. a bare `min_length` violation FastAPI
  itself raises before a custom validator runs) map to a generic
  `validation.invalid_field` key carrying `{ "field": <loc-joined-path> }> ` so
  nothing reaches the client unstructured.
- Every current `raise ValueError("...")` inside a `@field_validator`/
  `@model_validator` (`domain/models.py`, `export/serializers.py`,
  `api/routes/reviews.py`) becomes
  `raise PydanticCustomError("budget.warn_above_exceeds_max", "...", {"warn_above_usd": ..., "max_spend_usd": ...})`.
  The second argument (template) is never read by the frontend — pydantic
  requires it internally for its own error message, but the handler discards
  `msg` in favor of `type`/`ctx`.
- Rejected alternative — subclass `HTTPException` per error family (e.g.
  `BudgetError(HTTPException)`): rejected because it still requires every call
  site to build its own `detail` payload; a single `RevaiError` with two
  required fields is simpler and makes the contract impossible to bypass by
  construction (there's no `detail=` kwarg to misuse).
- Free-form runtime exceptions that currently forward raw system text
  (`GitError`, `StorageError`, `FolderPickerError`, Sonar's `ValueError`/
  `TimeoutError`) are recatalogued: each distinct raise site gets its own
  `error_key` and moves the dynamic part (path, branch name, timeout seconds,
  raw stderr/exception text) into `params`. Where the raw system message
  itself is genuinely useful for debugging (e.g. git stderr, YAML parse
  error), it is preserved as a `params.detail` string — the catalog's English
  template still names it as a "technical detail" line rather than the whole
  sentence, and the toast/banner renders it in a monospace secondary line, not
  as the primary message.

### 3. Frontend: `error_key → { en, pt }` catalog with `params` interpolation

- New `lib/errors.ts` module: `ERROR_CATALOG: Record<string, { en: string; pt: string }>` where each template uses `{paramName}` placeholders, e.g.
  `"budget.warn_above_exceeds_max": { en: "Warn threshold (${warn_above_usd}) can't exceed the maximum spend (${max_spend_usd}).", pt: "O limite de aviso ({warn_above_usd}) não pode ser maior que o gasto máximo ({max_spend_usd})." }`.
- `describeFailure()` in `lib/api.ts` is rewritten to parse the new
  `{ error_key, params }` shape (single object, or an array of them for
  multi-field validation failures — joined with `"; "` after each is resolved
  individually), resolve each through the catalog with the caller's current
  `locale`, and return the human sentence. `ApiError` gains an optional
  `errorKey`/`params` pair so a component can special-case a specific error if
  it ever needs to (e.g. highlighting the offending form field), without
  string-matching English text.
- Locale resolution reuses `useUiText()`'s existing `locale` state; `ApiError`
  formatting happens at the call site (inside a component, which already has
  `useUiText()` available) rather than inside `lib/api.ts` itself, keeping
  `lib/api.ts` framework-agnostic (it exports the raw `error_key`/`params`,
  not pre-rendered text) with a resolver helper `resolveApiError(error, locale)` exported from the new `lib/errors.ts`.
- Unmapped `error_key` (a future backend key the frontend hasn't caught up to
  yet) falls back to a generic per-locale message
  ("Something went wrong. (`{error_key}`)" / "Algo deu errado. (`{error_key}`)")
  rather than throwing or showing nothing — mirrors the existing
  fallback-to-English behavior of `t()`.

### 4. Toast/notification component

- New `components/ui/toast.tsx` (presentation) + `components/toast-provider.tsx`
  (state: FIFO queue, capped at 3, a `useToast()` hook exposing
  `push(message, tone)`). Mounted once near the app root (alongside
  `UiPreferenceProvider`) so any client component can call `useToast()`.
- Queue semantics: an array of `{ id, message, tone, createdAt, remainingMs }`.
  Pushing past 3 entries drops `queue[0]` (oldest) immediately — true FIFO
  eviction, not just capped rendering. Each toast owns a `setTimeout`-based
  countdown starting at 10000ms; on `onMouseEnter` the timeout is cleared and
  the remaining time is stored, on `onMouseLeave` a new timeout is scheduled
  for the remaining time — pause/resume, not reset.
- Positioning: fixed stack, bottom-right (consistent with `SaveBar` occupying
  bottom-center/left on settings pages, avoids overlap), `z-50`, rendered via
  a portal (`createPortal` into `document.body`) so it is never clipped by an
  `overflow-hidden` ancestor (several `Card`s use `overflow-hidden`).
- Theme-inverted color: two new **theme-independent** CSS custom properties
  defined once in `globals.css` outside the `@theme`/`[data-theme]` remapping
  blocks — `--color-toast-bg` / `--color-toast-ink` — set directly (not
  derived from `--color-paper`/`--color-ink`) so they don't get remapped by
  `html[data-theme="dark"]`:
  - Default (page is light): `--color-toast-bg: #0a0a0b` (zinc-950),
    `--color-toast-ink: #fafafa` (zinc-50).
  - `html[data-theme="dark"]` and the `prefers-color-scheme` system-dark
    block: `--color-toast-bg: #e4e4e7` (zinc-200), `--color-toast-ink: #18181b`
    (zinc-900).
  - Severity is still conveyed the existing way (icon + a thin left accent
    bar in `--color-critical`/`--color-medium`/`--color-success`, which already
    have light/dark values), not by changing the toast's base surface color —
    the base surface's job is only "this floats above the page, always high
    contrast," matching the requirement that it look distinct from both
    `SaveBar` (light) and the page itself in either theme.
- Rejected alternative — reuse `Card`'s `bg-paper` and let dark mode remap it:
  rejected explicitly per requirement — the user wants the toast to *invert*
  relative to page theme, which `bg-paper` cannot do since it's defined to
  move *with* the theme.

### 5. Migrating existing inline error banners to toast

- `project-workspace.tsx`'s `notice` state (project list + review setup),
  `provider-panel.tsx`'s `reason`, `insights-dashboard.tsx`'s `error`,
  `export-data-panel.tsx`'s `error`, and the open/clone-project dialog's
  `error` state all call `useToast().push(...)` at the point they currently
  call `setNotice`/`setError`, instead of rendering a local `<div>` banner.
  The local `error`/`notice` state itself can be removed once nothing renders
  from it directly (kept only where a field-level inline hint is still useful,
  e.g. highlighting an invalid destination path in the clone dialog — that
  remains inline per the decision that modal-local, field-scoped errors are
  not toast candidates, but the *dialog's* top-level operation failure, e.g.
  "clone failed: repository not found", *is* a toast).
- `SaveBar` (settings save flow) and the two settings "page failed to load"
  screens are explicitly excluded from this migration (see Decision 6).

### 6. Settings "backend unreachable" recovery screen

- New shared component `components/backend-unreachable.tsx` used by both
  `app/settings/appearance/page.tsx` and `app/settings/engine/page.tsx` in
  place of today's bare `"Preferences unavailable"` block. Takes the caught
  `reason` (already resolved via `resolveApiError`/`Error.message`) as a prop.
- Layout: icon + heading ("Can't reach the RevAI backend" /
  "Não foi possível conectar ao backend do RevAI"), one explanatory sentence
  naming the expected address (`API_BASE_URL`, already exported from
  `lib/api.ts`) and that it usually means the Docker container isn't running,
  a `surface-sunken` monospace block with the two suggested commands
  (`docker compose ps`, `docker compose logs api --tail=100`), a raw
  technical-detail line (the `reason` string, monospace, secondary emphasis),
  and two actions: **"Copy AI troubleshooting prompt"** (primary, copies to
  clipboard via `navigator.clipboard.writeText`, already used in
  `project-workspace.tsx`'s patch-copy feature — shows a transient "Copied"
  state on the button itself, 1.5s, matching that existing pattern) and
  **"Try again"** (secondary, re-runs the page's server-side fetch — since
  these are server components today, this becomes a client "retry" button
  that calls `router.refresh()`).
- The prompt text is generated by a pure function
  `buildTroubleshootingPrompt(reason: string): string` (co-located in
  `backend-unreachable.tsx`), interpolating the live `reason` into the fixed
  template agreed with the user (names `docker-compose.yml`'s `api` service,
  port 8799, `/api/health`, and the four remediation steps). It is composed in
  English regardless of `ui.locale` — the target audience is the user's coding
  agent, not the user, and troubleshooting prompts aimed at an AI agent were
  explicitly agreed to stay off-screen and are lower-value to translate; this
  is called out as an explicit scope decision, not an oversight.

## Risks / Trade-offs

- **[Risk]** Breaking the API response contract with no compatibility shim
  means backend and frontend must ship atomically; a partial deploy (old API
  container + new web container, or vice versa) breaks every error path.
  → **Mitigation**: both live in the same `docker-compose.yml` and the same
  repo/CI pipeline (`platform-ci.yml`); call this out explicitly in the
  rollout step of `tasks.md` so it's never deployed piecemeal.
- **[Risk]** Cataloguing ~45 distinct raise sites into `error_key`s is
  mechanical, repetitive work with high chance of an inconsistent naming
  scheme if done ad hoc. → **Mitigation**: the design fixes the
  `<domain>.<reason>` convention up front and `tasks.md` will enumerate the
  full key list per file before any code changes, so naming is decided once
  and reviewed as data, not discovered mid-implementation.
- **[Risk]** A future backend change could ship an `error_key` the frontend
  catalog doesn't know yet (e.g. a hotfix). → **Mitigation**: the designed
  fallback (generic message + raw key shown) degrades safely instead of
  crashing or showing blank text.
- **[Risk]** Toast auto-dismiss racing with FIFO eviction (a toast is evicted
  by a 4th arrival while the user is hovering it, mid-pause) could feel
  abrupt. → **Mitigation**: eviction always removes the oldest queue entry
  regardless of hover state — this is the explicit, agreed behavior — but the
  removal is animated (fade/slide, not an instant unmount) so it never looks
  like a glitch.
- **[Trade-off]** Keeping the AI troubleshooting prompt English-only is a
  deliberate simplicity trade-off agreed with the user; if the user later
  wants it localized, the same `ERROR_CATALOG` mechanism can be extended to
  it without restructuring.

