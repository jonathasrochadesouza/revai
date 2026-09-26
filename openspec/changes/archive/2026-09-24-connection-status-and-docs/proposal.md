## Why

RevAI tells the user whether it can actually run a review in the wrong places and
at the wrong times. The projects screen carries an "API connected" chip that says
nothing about the AI provider — the part that decides whether a review can run at
all — while a broken provider stays invisible until a review fails. The recovery
guidance that does exist (`BackendUnreachable`) only appears when a settings page's
server-side fetch happens to fail, and there is no in-product documentation at all:
the one thing a user needs when the backend is down ("how do I start it?") lives in
a README outside the app.

## What Changes

- **New aggregated status endpoint** `GET /api/status`, returning the backend's own
  health, an AI verdict derived from the configured provider plus the full provider
  scoreboard, and the local SonarQube state. Results are served from a short-lived
  in-process cache so the CLI-probing sweep is not re-run on every page view;
  `?refresh=true` bypasses the cache for explicit re-checks.
- **New settings screen `/settings/connection` ("API & AI" / "API e IA")**: live
  status of the backend, of every AI provider, and of local SonarQube, with the
  remediation the backend already reports, a re-check action, a link to
  `/settings/engine` for configuration, and a link to the backend startup
  documentation.
- **New global warning banner**, full width directly under the top bar, small
  height, amber (`medium` tone), alert icon, one short message, one clean action
  linking to `/settings/connection`, and a dismiss control. It renders nothing
  until the first status answer arrives, alerts only after a debounce so a backend
  restart does not flash a warning, and never appears on `/settings/connection`
  itself.
- **New in-app documentation section `/docs`** with a left sidebar and nine pages,
  fully static and translated through the message catalog, so it stays readable
  with the backend down and with no internet connection.
- **Primary navigation restructured**: `Data` and `Appearance` stop being
  duplicated as both top-level entries and Settings dropdown entries; `Docs` gains
  a top-level entry; `API & AI` joins the Settings dropdown.
- **Removed**: the `API connected` / `API unreachable` chip on the projects screen
  (`ApiStatusBadge`), superseded by the banner and the new screen.

## Capabilities

### New Capabilities
- `connection-status`: one aggregated, cached view of whether RevAI can run a
  review right now — backend reachability, AI provider readiness (verdict driven by
  the configured provider, scoreboard covering all of them), and optional local
  SonarQube — surfaced both as a dedicated settings screen and as a global,
  dismissible warning banner.
- `documentation-pages`: an in-app, multi-page documentation section with sidebar
  navigation that works with the backend stopped and without internet access.
- `shell-navigation`: the structure of the application's primary navigation —
  which destinations are top-level, which live under Settings, and where
  connection status is (and is no longer) surfaced.

### Modified Capabilities
<!-- None: openspec/specs/ is empty, so no main spec requirements change. The
     in-progress `friendly-error-messages` change owns
     `backend-unreachable-recovery`; this change reuses that screen's component
     rather than altering its requirements. -->

## Impact

**Backend** (`platform/api/revai`)
- New route module for `GET /api/status`; new cached status service composing
  `ProviderRegistry.health_all()`, the health/runtime data, and the SonarQube
  status probe. No change to provider probing itself (it already runs
  concurrently) and no new dependency.

**Web** (`platform/web/src`)
- New: `app/settings/connection/`, `app/docs/` (layout, `[slug]` route, page
  registry, sidebar), a connection-status context provider mounted in
  `app/layout.tsx`, and a banner rendered inside `components/top-bar.tsx`.
- Modified: `app/layout.tsx`, `components/top-bar.tsx` (banner slot, nav
  restructure, `SETTINGS_MENU`), `app/page.tsx` (chip removed),
  `components/page-header.tsx` (new settings page variant), `lib/api.ts` (status
  types and call).
- Removed: `components/api-status-badge.tsx`.
- i18n: new `docs.*` and `connection.*` keys; docs prose split into dedicated
  catalog modules merged into the existing catalogs so `MessageKey` and the
  parity test keep covering them. Commands and product names stay outside the
  catalog as TSX constants, since the parity test forbids identical strings
  across locales.

**Docs/README**
- `README.md` and the new `run-the-backend` page must tell the same startup story,
  with Docker Compose as the primary path and `uv run revai-api` as the
  development path.
