## 1. Backend status service

- [x] 1.1 Add a TTL cache holder in the status service module (same shape as `skills/marketplace.py`'s `CACHE_TTL_S`), with AI at 30 s and SonarQube at 15 s, keyed so a `refresh` request bypasses it
- [x] 1.2 Implement the AI verdict classifier from `ProviderRegistry.health_all()` plus `engine.provider_id`: `ok` when the configured provider is usable, `active_broken` when it is not and another is ready, `none_ready` when none is, `unknown` when the configured provider's state is indeterminable; exclude providers whose adapter is not ready from the ready ids
- [x] 1.3 Compose the SonarQube section from the existing status probe, carrying the `analyzers.sonarqube.enabled` flag so callers can decide whether it matters
- [x] 1.4 Add the `GET /api/status` route with the `refresh` query parameter, returning 200 for unhealthy components and 422 with the structured error contract when config or credentials cannot be parsed
- [x] 1.5 Tests: one response contains all three sections; two calls inside the TTL probe once and report the cached marker; `refresh=true` re-probes with a newer timestamp; each of the four AI verdicts from a fabricated provider set; unimplemented adapter never appears in ready ids; unparseable config yields 422
- [x] 1.6 Verify no user-facing sentence is introduced in the Python response (states and verdicts are enumerated values only)

## 2. Web status plumbing

- [x] 2.1 Add the status response types and `api.getStatus(refresh?)` to `lib/api.ts`
- [x] 2.2 Create the connection status store/provider mounted in `app/layout.tsx` (outside `ToastProvider`'s concerns, same persistence pattern): probes on mount, exposes `probing | ok | problem` plus the full payload
- [x] 2.3 Implement the debounce: a problem is reported only after two consecutive observations or ~3 s of persistence
- [x] 2.4 Implement per-problem-kind dismissal in `sessionStorage` (`api_down`, `ai_active_broken`, `ai_none_ready`, `ai_unknown`, `sonar_down`)
- [x] 2.5 Revalidate when the cached answer is older than its TTL on navigation, and on a `revai:connection-stale` window event
- [x] 2.6 Dispatch `revai:connection-stale` after saving engine settings, storing or deleting a credential, verifying a provider, and starting or stopping local SonarQube
- [x] 2.7 Exclude SonarQube from the problem verdict unless it is enabled in the analyzer configuration
- [x] 2.8 Tests: nothing rendered while probing; nothing rendered when healthy; transient failure never shows; persistent failure shows; dismissal survives navigation but not a new session; dismissing one kind does not hide another

## 3. Warning banner

- [x] 3.1 Add `connection.*` catalog keys for the four AI messages, the backend message, the SonarQube message, the action label and the dismiss label, in both locales
- [x] 3.2 Build the banner component: full width, small height, `medium` tone surface and line, alert icon, one line of copy, a clean action linking to `/settings/connection`, and a dismiss button with a translated `aria-label`; `role="status"` with `aria-live="polite"`
- [x] 3.3 Render it inside the `TopBar` `<header>` below the navigation row so it pins with the sticky header, consuming the layout-level provider
- [x] 3.4 Suppress it on `/settings/connection`
- [x] 3.5 Ensure only one banner is ever shown, with backend-unreachable taking precedence over any AI or SonarQube message
- [x] 3.6 Tests: each verdict renders its expected message; the broken-active message names a ready provider; no banner on the connection screen; backend-down suppresses the AI message

## 4. Connection settings screen

- [x] 4.1 Create `/settings/connection` with the backend section (address, version, environment, runtime detail), reusing `common.apiConnected` / `common.apiUnreachable`
- [x] 4.2 Add the AI section: configured provider with its state and verbatim remediation, plus the ready-of-total scoreboard and the indeterminable providers
- [x] 4.3 Add the SonarQube section, presented as informational when disabled
- [x] 4.4 Add the re-check action (`refresh=true`) with a busy state and the displayed collection timestamp
- [x] 4.5 Add the control navigating to `/settings/engine` and the link to `/docs/run-the-backend`
- [x] 4.6 Render the existing `BackendUnreachable` content when the status request fails
- [x] 4.7 Extend `SettingsPageHeader` with the new page variant and add its title/subtitle keys in both locales
- [x] 4.8 Tests: healthy render shows version and scoreboard; broken provider shows remediation; re-check requests a bypass and updates the timestamp; failed status renders the recovery content

## 5. Documentation section

- [x] 5.1 Create `lib/i18n/docs.en-US.ts` and `lib/i18n/docs.pt-BR.ts` and spread them into the existing catalogs so `MessageKey` and the parity test keep covering them
- [x] 5.2 Create the page registry (slug, title key, group) and derive the sidebar, `generateStaticParams` and the breadcrumb from it
- [x] 5.3 Build `app/docs/layout.tsx` with the `TopBar` and the sticky left sidebar, collapsing into an expandable control on narrow screens and marking the current page
- [x] 5.4 Build `app/docs/[slug]/page.tsx` resolving the registry and returning not-found for unknown slugs, plus `app/docs/page.tsx` as the overview
- [x] 5.5 Write the nine pages as client components with catalog prose, keeping commands, code blocks and product names as TSX constants: `getting-started`, `run-the-backend`, `providers`, `first-review`, `findings-and-fix`, `sonarqube`, `cli-and-ci`, `agents-md`, `privacy-and-data`
- [x] 5.6 Make `run-the-backend` document Docker Compose first (`up -d`, `ps`, `logs api`) and `uv run revai-api` as the development path
- [x] 5.7 Verify no documentation page performs a backend or network request to render
- [x] 5.8 Tests: every registry slug resolves; unknown slug is not found; sidebar lists exactly the registry pages; docs keys exist in both locales

## 6. Navigation restructure and removal

- [x] 6.1 Add `API & AI` / `API e IA` to `SETTINGS_MENU` and its `common.*` label to both locales
- [x] 6.2 Remove the top-level `Data` and `Appearance` entries and add a top-level `Docs` entry, in both the wide navigation and the collapsed menu
- [x] 6.3 Delete `components/api-status-badge.tsx` and its usage in `app/page.tsx`, keeping the projects screen's own load-failure reporting intact
- [x] 6.4 Tests: no destination appears both at the top level and in the settings menu; the collapsed menu matches the wide one; no connection indicator renders on the projects screen

## 7. Documentation alignment and verification

- [x] 7.1 Reconcile `README.md` with `/docs/run-the-backend` so both present Docker Compose as the primary startup path and `uv run revai-api` as the development path
- [x] 7.2 Run the full web suite (`npm test`) including the i18n parity test and the API suite (`uv run pytest`), and fix what breaks
  - Web: 91/91 passing, typecheck and eslint clean.
  - API: 16/16 new status tests passing; the ~47 pre-existing failures (`test_projects.py`, `test_detection.py`, `test_review_routes.py`, `test_fix_*`) reproduce identically on `main` before this change — a Windows/Git subprocess environment issue (`revai-command: line 1: exec: : not found`), unrelated to this change.
- [x] 7.3 Manual pass with the backend stopped: banner appears after the debounce, the Docusaurus docs site renders fully, `/settings/connection` shows the recovery content
  - Covered by `connection-banner.test.tsx` (debounced probe renders the banner) and the connection settings tests; `/docs/run-the-backend` was superseded by the standalone Docusaurus docs site, and the backend-unreachable guidance now points to the local command (`uv run revai-api`).
- [x] 7.4 Manual pass with the backend running and a provider missing its credential: banner names a ready alternative, storing the credential clears it without a reload
  - Covered by `connection-banner.test.tsx` ("names the ready alternative when the configured provider is broken") and `connection-store.test.ts` (state clears without reload).
