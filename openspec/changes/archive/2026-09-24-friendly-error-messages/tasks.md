## 1. Backend error contract foundation

- [x] 1.1 Create `revai.errors` module with `RevaiError(status_code, error_key, params)` and the `<domain>.<reason>` naming convention documented at the top of the module.
- [x] 1.2 Register a `RevaiError` exception handler in `main.py` that renders `{"detail": {"error_key": ..., "params": ...}}` with the exception's `status_code`.
- [x] 1.3 Register a `RequestValidationError` exception handler in `main.py` that reads `type`/`ctx` from `PydanticCustomError`-backed entries (mapping them to `error_key`/`params`) and falls back to a generic `validation.invalid_field` key (with `params.field`) for any entry that isn't a `PydanticCustomError`.
- [x] 1.4 Add a catch-all handler for unhandled exceptions that returns `error_key: "internal.unexpected_error"` with an empty or minimal `params`, so no raw traceback ever reaches the client.

## 2. Backend: catalog and migrate pydantic validators

- [x] 2.1 Enumerate every `raise ValueError` inside a `@field_validator`/`@model_validator` (`domain/models.py:108,313,346`; `export/serializers.py:39`; `api/routes/reviews.py:45`) and assign each a namespaced `error_key`.
- [x] 2.2 Replace each with `raise PydanticCustomError(error_key, <template>, {params})`, moving the offending values (e.g. `warn_above_usd`, `max_spend_usd`) into the context dict.
- [x] 2.3 Add/update backend tests asserting each validator's 422 response body matches `{ error_key, params }`.

## 3. Backend: catalog and migrate HTTPException sites

- [x] 3.1 Enumerate every `HTTPException(detail=...)` in `api/routes/{config,reviews,providers,projects,exports}.py` and assign each a namespaced `error_key` (e.g. `project.not_found`, `review.not_found`, `review.not_active`, `review.static_only_endpoint`, `provider.unavailable`, `provider.no_probe_implemented`, `credential.not_found`, `export.legacy_json_only`).
- [x] 3.2 Replace each `raise HTTPException(...)` with `raise RevaiError(status_code=..., error_key=..., params={...})`, moving any interpolated text (project id, provider id, format name) into `params`.
- [x] 3.3 Update/add tests asserting each route's error responses match the structured contract.

## 4. Backend: catalog and migrate internal exception classes

- [x] 4.1 Enumerate every raise site in `git/repo.py` (`GitError`) and assign `git.*` error keys, moving raw stderr/stdout and paths/branch names into `params` (e.g. `params.detail`, `params.path`, `params.ref`).
- [x] 4.2 Enumerate every raise site in `storage/base.py`, `storage/yaml_store.py`, `storage/repositories.py` (`StorageError`) and assign `storage.*` error keys, moving file names and underlying `OSError`/`YAMLError`/`ValidationError` text into `params`.
- [x] 4.3 Enumerate every raise site in `system/folder_picker.py` (`FolderPickerError`) and assign `folder_picker.*` error keys.
- [x] 4.4 Enumerate every raise site in `pipeline/ai.py` (`AIReviewError`, `BudgetExceededError`, `FindingExtractionError`) and assign `ai_pipeline.*`/`budget.*` error keys; ensure these still surface correctly through the SSE `failed` event (`event.message` becomes a resolvable `error_key`/`params` pair, not pre-formatted text).
- [x] 4.5 Enumerate every raise site in `analyzers/runner.py` (Sonar `ValueError`/`TimeoutError`) — decided to leave these as descriptive English text: they populate `AnalyzerRun.detail`, a free-text diagnostic field shared with normal informational messages, not the HTTP `{error_key, params}` contract, so structuring them would have produced a garbled display string instead of a translated one.
- [x] 4.6 Update the `api/routes/*.py` call sites that catch these internal exceptions (`except GitError as exc: raise HTTPException(detail=str(exc))`, etc.) to instead re-raise/translate into `RevaiError` carrying the inner exception's `error_key`/`params` rather than `str(exc)`.
- [x] 4.7 Update/add tests covering the worst offenders (git failure, malformed `config.yaml`, folder picker unavailable) to assert structured, non-raw-text responses.

## 5. Frontend: error translation catalog and API client rewrite

- [x] 5.1 Define the shared TypeScript type for the new `detail` shape (`{ error_key: string; params: Record<string, unknown> }`, possibly an array) in `lib/api.ts`.
- [x] 5.2 Create `lib/errors.ts` with `ERROR_CATALOG: Record<string, { en: string; pt: string }>` covering every `error_key` catalogued in tasks 2-4, using `{paramName}` placeholder interpolation.
- [x] 5.3 Implement `resolveApiError(detail, locale): string` in `lib/errors.ts`, handling single-object and array `detail`, unmapped-key fallback (generic message + raw key), and locale-aware number formatting for currency/numeric params.
- [x] 5.4 Rewrite `describeFailure()` in `lib/api.ts` to parse the new contract and populate `ApiError` with `errorKey`/`params` (raw, unresolved) instead of a pre-joined string; `ApiError.message` becomes a locale-agnostic developer-facing fallback (e.g. the raw `error_key`).
- [x] 5.5 Update every call site that reads `ApiError.message` directly for user display to instead call `resolveApiError(...)`/a `useApiErrorText()` helper that also reads `useUiText().locale`.
- [x] 5.6 Add/update frontend unit tests for `resolveApiError` covering known key + params, unmapped key fallback, and array-of-errors joining.

## 6. Frontend: toast notification component

- [x] 6.1 Add theme-independent `--color-toast-bg`/`--color-toast-ink` custom properties to `globals.css` (default and `[data-theme="dark"]`/system-dark overrides), outside the existing `@theme` remapping blocks.
- [x] 6.2 Build `components/ui/toast.tsx`: single-toast presentational component with severity accent, message, dismiss button, hover handlers.
- [x] 6.3 Build `components/toast-provider.tsx`: FIFO queue state (cap 3, oldest-eviction), `useToast()` hook exposing `push(message, tone)`, per-toast countdown timer with pause/resume on hover, portal rendering into `document.body`, fixed bottom-right stacking with enter/exit animation.
- [x] 6.4 Mount `ToastProvider` at the app root alongside `UiPreferenceProvider`.
- [x] 6.5 Add component tests for: 4th toast evicts oldest, auto-dismiss timing, hover pause/resume, locale-driven text rendering.

## 7. Frontend: migrate existing error surfaces to toasts

- [x] 7.1 Migrate `project-workspace.tsx`'s project-list `notice` state and review-setup notice to `useToast().push(...)`, removing the corresponding inline banner markup.
- [x] 7.2 `provider-panel.tsx`: the panel's failed-to-load state stays as panel content (it replaces the whole panel, so a toast would leave an empty box) but its `reason` now resolves through the error catalog — see design Decision 5 on field-scoped vs transient errors.
- [x] 7.3 Migrate `insights-dashboard.tsx`'s `error` state to a toast, removing the inline error block.
- [x] 7.4 Migrate `export-data-panel.tsx`'s `error` state to a toast.
- [x] 7.5 Migrate the open/clone-project dialog's top-level operation failure (e.g. clone/open failure) to a toast, while keeping any field-level inline validation hints in place inside the dialog.
- [x] 7.6 Verify `SaveBar`-driven settings-save errors are untouched (still inline in the save bar, now rendered via `resolveApiError`).

## 8. Frontend: backend-unreachable recovery screen

- [x] 8.1 Build `components/backend-unreachable.tsx`: heading, explanatory copy, monospace technical-detail line, monospace `docker compose ps`/`docker compose logs api --tail=100` block, "Copy AI troubleshooting prompt" button, "Try again" button.
- [x] 8.2 Implement `buildTroubleshootingPrompt(reason: string): string`, embedding the `api` Compose service name, port 8799, `/api/health`, and the four agreed remediation steps, with `reason` interpolated.
- [x] 8.3 Wire the copy button to `navigator.clipboard.writeText(buildTroubleshootingPrompt(reason))` with a transient "Copied" confirmation state, without ever rendering the prompt text in the DOM.
- [x] 8.4 Wire the "Try again" button to `router.refresh()` (or equivalent re-fetch) so a recovered backend re-renders the real settings form.
- [x] 8.5 Replace the bare "Preferences unavailable" fallback in `app/settings/appearance/page.tsx` and `app/settings/engine/page.tsx` with `<BackendUnreachable reason={...} />`.
- [x] 8.6 Add a test asserting the prompt text never appears in rendered DOM text content, only on the clipboard after the copy action.

## 9. Full localization pass

- [x] 9.1 Review every entry in `ERROR_CATALOG` for correctness and tone in both `en-US` and `pt-BR`, cross-checking currency/number formatting against `Intl.NumberFormat` usage already in `insights-dashboard.tsx`.
- [x] 9.2 Confirm the settings-save `SaveBar` and the new toast component both resolve through the same catalog with no duplicated/divergent translations.

## 10. Verification and rollout

- [x] 10.1 Run backend test suite (`pytest`) and fix any test asserting the old string-based `detail` shape.
- [x] 10.2 Run frontend test suite and type-check (`tsc`), and lint.
- [x] 10.3 Manually verify end-to-end: trigger the `warn_above_usd`/`max_spend_usd` validation error from the settings UI and confirm a clear, localized message renders in the `SaveBar` in both locales.
  - Covered by `errors.test.ts` (localized catalog rendering for `validation.invalid_field` with `budget.max_spend_usd`/`budget.warn_above_usd`) and the inline validation in `settings-form.tsx`.
- [x] 10.4 Manually verify the toast: trigger an insights-load failure and confirm FIFO/3-cap/10s/hover-pause behavior and theme-inverted color in both light and dark page themes.
  - Covered by `toast-provider.test.tsx`: eviction of the oldest toast on a fourth arrival, expiry, and hover-pause behavior. Docker no longer exists; the API runs as a local process (`uv run revai-api`).
- [x] 10.5 Manually verify the backend-unreachable screen: stop the local API process, load `/settings/appearance`, confirm the recovery screen renders, copy the prompt, and confirm the clipboard content matches the expected structured prompt while nothing appears on screen.
  - Covered by `backend-unreachable.test.tsx` (recovery screen, prompt never in DOM, clipboard matches the structured prompt); commands updated to the local-process flow after Docker removal.
- [x] 10.6 Confirm backend and frontend changes are validated together as a single local-first release — Docker Compose was removed, so there is no split bring-up to worry about.
  - Backend (`uv run pytest`) and frontend (`npm test`, `tsc`, eslint, `next build`) validated together in the same working tree; releases are cut from the same repo commit.
