## Why

Every user-facing error in RevAI is currently a raw technical string: pydantic
validators leak `"budget: Value error, warn_above_usd must not exceed
max_spend_usd"` straight from the 422 response, `HTTPException` details mix
plain English with unformatted `OSError`/`YAMLError`/git-stderr text, and none
of it is translated even though the product already ships an English/Brazilian
Portuguese locale switch (`ui.locale`) for its interface labels. Errors are the
moment a user is most likely to be confused or stuck, and today that moment is
also the least polished part of the product. There is also no consistent way
to surface an error that happens outside the settings save flow — every screen
invents its own inline red banner.

## What Changes

- **BREAKING**: replace the API's error response contract. Every `4xx`/`5xx`
  response now returns a structured `detail` object
  `{ "error_key": "<namespace>.<reason>", "params": { ... } }` instead of a
  plain string or a raw pydantic error array. No backward-compatible fallback
  is kept — frontend and backend ship together in this change.
- Introduce a central FastAPI exception handler that converts every raised
  error (a new `RevaiError(error_key, params)` for `HTTPException`-style
  cases, and `PydanticCustomError` for model/field validators) into that
  contract. No route handler formats error text directly anymore.
- Catalog and assign a stable `error_key` to every current user-facing error
  site across `domain/models.py`, `api/routes/*.py`, `storage/*.py`,
  `git/repo.py`, `system/folder_picker.py`, `pipeline/ai.py`,
  `analyzers/runner.py`.
- Add a frontend `error_key → { en, pt }` translation catalog (parallel to the
  existing `PT_BR` navigation dictionary) that interpolates `params` into a
  human-readable, locale-aware sentence. Unknown/unmapped keys fall back to a
  generic "something went wrong" message rather than raw text.
- Introduce a new dark, floating toast/notification component: FIFO queue,
  max 3 visible at once (a 4th arrival evicts the oldest), 10s auto-dismiss
  per toast, timer pauses on hover and resumes on mouse leave. Colors invert
  against the page theme (near-black on a light page, light-gray on a dark
  page) so it always reads as a distinct, elevated surface regardless of
  `ui.theme`.
- Migrate every error surface that is *not* the settings-save flow to the new
  toast: the project list/workspace notice banner, review setup notices,
  insights dashboard, data export panel, provider panel, and the open/clone
  project dialog's inline error.
- Keep `SaveBar`'s existing light, sticky, bottom-of-page error presentation
  exactly as-is for settings save actions (`appearance-form.tsx`,
  `settings-form.tsx`) — translated via the same catalog, but not migrated to
  the toast.
- Redesign the settings pages' "backend unreachable" fallback (currently a
  bare `Preferences unavailable` block) into a full, polished recovery screen:
  explains the Docker container is unreachable, shows the technical reason in
  monospace, suggests `docker compose ps` / `docker compose logs api`, and
  adds a "Copy AI troubleshooting prompt" button that copies a structured,
  Docker-Compose-aware prompt to the clipboard without ever displaying it on
  screen.

## Capabilities

### New Capabilities
- `error-catalog`: backend error contract (`error_key`/`params`), the central
  exception handler, and the full inventory of assigned error keys across the
  API.
- `toast-notifications`: the FIFO/max-3/10s/hover-pause dark toast component
  and its integration points across non-settings-save error surfaces.
- `backend-unreachable-recovery`: the redesigned settings fallback screen and
  its copyable AI troubleshooting prompt.

### Modified Capabilities
- None. No existing `openspec/specs/` capabilities exist yet in this project
  (this is the first OpenSpec change), so all affected behavior is captured as
  new capabilities above.

## Impact

- **Backend** (`platform/api/revai`): `main.py` (new exception handler
  registration), `domain/models.py`, `api/routes/{config,reviews,providers,
  projects,exports}.py`, `storage/{base,yaml_store,repositories}.py`,
  `git/repo.py`, `system/folder_picker.py`, `pipeline/ai.py`,
  `analyzers/runner.py`. New module for `RevaiError` and the `error_key`
  registry.
- **Frontend** (`platform/web/src`): `lib/api.ts` (`describeFailure` rewrite,
  new error contract types), new `components/ui/toast.tsx` +
  `components/toast-provider.tsx`, `components/ui-preference-bootstrap.tsx`
  (extended catalog), `components/projects/project-workspace.tsx`,
  `components/provider-panel.tsx`, `components/insights/insights-dashboard.tsx`,
  `components/data/export-data-panel.tsx`, `app/settings/engine/page.tsx`,
  `app/settings/appearance/page.tsx` (new unreachable-backend screen).
- **API contract**: this is a breaking change to the shape of every non-2xx
  JSON response body. No API versioning exists yet, so this ships as a direct
  replacement.
- **i18n**: extends the existing `ui.locale` mechanism; no new locale is
  introduced, only new translated content within `en-US`/`pt-BR`.
