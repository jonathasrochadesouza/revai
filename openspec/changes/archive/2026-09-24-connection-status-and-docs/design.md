## Context

Two facts about the current code shape this design.

**Provider probing is expensive and already parallel.** `ProviderRegistry.health_all()`
probes all eight providers with `asyncio.gather`, three of them by spawning CLI
subprocesses (`claude`, `copilot`, `kiro-cli`) with a 20-second ceiling each. The
existing `ProviderPanel` is a client component precisely so this never blocks a
server render. There is no cache anywhere in the provider path, so every
`GET /api/providers` re-runs the sweep. A banner that must be present on every
screen therefore cannot call `/api/providers` per navigation.

**The web shell has no persistent client component below the layout.** Every route
renders its own `<TopBar>` (including the `loading.tsx` skeletons), so top-bar state
is destroyed on each navigation. `app/layout.tsx` is the only component that
survives navigation, and it already hosts this exact pattern for toasts
(`ToastProvider` wrapping the tree, a module-scoped store outside React).

Constraints inherited from the product: repository content never leaves the machine,
the app must work with no internet connection (fonts are self-hosted for this
reason), the interface ships two complete locales, and `i18n.test.ts` enforces
pt-BR/en-US key parity *and* rejects entries whose pt-BR text is identical to en-US.

## Goals / Non-Goals

**Goals:**
- One cheap, cacheable question — "can RevAI run a review right now?" — answerable
  from any screen without re-spawning CLI probes.
- A banner that is honest (never green when a review would fail), quiet (no flash on
  restart, no nagging after dismissal), and actionable (one click to the fix).
- Documentation that is readable exactly when the user needs it most: backend
  stopped, no internet.
- A navigation structure with no duplicated destinations.

**Non-Goals:**
- Replacing `ProviderPanel` or the engine configuration form. `/settings/connection`
  diagnoses; `/settings/engine` configures.
- Replacing the `BackendUnreachable` recovery screen owned by the in-progress
  `friendly-error-messages` change. This change reuses that component.
- Real-time push (WebSocket/SSE) status. Polling a cached endpoint is enough.
- Docs authored as Markdown, MDX, or fetched from the backend.
- Provisioning or starting anything automatically (no "start backend for me" button).

## Decisions

### D1 — One aggregated `GET /api/status`, cached in-process with a per-section TTL

The banner needs a single coarse answer; the settings screen needs the detail. Both
come from one endpoint so there is one source of truth and one round trip.

```
GET /api/status              → serves from cache when fresh
GET /api/status?refresh=true → bypasses the cache (re-check button)

{
  "api":  { "status": "ok", "version": "…", "environment": "…" },
  "ai":   { "active_provider_id": "anthropic",
            "active_state": "needs_auth",
            "active_usable": false,
            "ready_provider_ids": ["ollama"],
            "unknown_provider_ids": ["copilot_cli"],
            "total": 8,
            "verdict": "active_broken" },
  "sonarqube": { "enabled": true, "server_up": false, "detail": "…" },
  "checked_at": "…", "from_cache": true, "ttl_s": 30
}
```

TTLs: AI 30 s, SonarQube 15 s, api section always live (the request answering proves
it). The cache is a small in-process TTL holder, the same shape already used by
`skills/marketplace.py` (`CACHE_TTL_S`) — no new pattern, no new dependency, and it
dies with the process, which is correct for a local single-user tool.

*Alternatives considered.* (a) Banner calls `/api/providers` directly: rejected, it
re-spawns three subprocesses per navigation. (b) Client-side cache only, no backend
change: the first render of every browser tab still pays the full sweep, and the CLI
would not benefit from the same verdict logic. (c) Background refresh task on a
timer: keeps subprocesses running when nobody is looking, for a tool that is idle
most of the time.

### D2 — The AI verdict is driven by the configured provider; the scoreboard covers all

A review runs with `engine.provider_id`. "Some provider somewhere is ready" is
therefore not a safe green: Anthropic without a key plus Ollama ready would show
"connected" while every review fails.

```
                   active ready/unknown │ active broken
 ─────────────────┼─────────────────────┼──────────────────────────────
 another ready    │ verdict: ok         │ verdict: active_broken
                  │ (no banner)         │ message names the ready one
 none ready       │ verdict: ok         │ verdict: none_ready
```

`active_state: unknown` (GitHub Copilot CLI ships no auth-status command and exits 0
on invalid input) is its own verdict value, `unknown` — it does alert, with copy that
says the state could not be confirmed rather than claiming a failure.

The backend returns facts plus the coarse `verdict` enum; every user-facing sentence
lives in the web catalog. Domain classification is reusable by the CLI; UI copy in
Python would be untranslatable.

### D3 — Status lives in a layout-level provider; the banner renders inside `TopBar`

```
app/layout.tsx
└─ ConnectionStatusProvider      ← survives navigation: probes once, owns dismissal
   └─ ToastProvider
      └─ {children}
          └─ TopBar (per route)
             ├─ bar row (wordmark · breadcrumb · nav)
             └─ ConnectionBanner   ← consumes context, inside the sticky <header>
```

The banner must sit visually under the nav and span the full width, and the state
must outlive navigation. Splitting the two — state in the layout, presentation in the
top bar — is the only arrangement that gives both. Putting the banner in the layout
would place it above the top bar; keeping state in `TopBar` would re-probe and undo
the dismissal on every route change.

The banner is inside the sticky `<header>`, so it stays pinned while scrolling and
adds a permanent ~28 px band only while a problem exists.

### D4 — Three display states, and the banner renders nothing until the first answer

```
probing ──first answer──▶ ok        (renders nothing)
   │                       │
   │                       └─problem persists past debounce──▶ warning
   └─ renders nothing (no skeleton, no layout shift)
```

Debounce: a problem must be observed twice in a row, or persist ~3 s, before the
banner appears. Restarting the backend is routine during development and a warning
that flashes on every restart trains users to ignore it. The backend still reports
the raw truth; the delay is purely presentational.

Dismissal is stored in `sessionStorage`, keyed by the *verdict class* (`api_down`,
`ai_active_broken`, `ai_none_ready`, `ai_unknown`, `sonar_down`). Dismissing "backend
down" must not silence "provider needs auth" that appears later; a new tab starts
clean; `localStorage` was rejected because it would let a user permanently hide a
condition that breaks reviews.

The banner is suppressed on `/settings/connection`, where the user is already looking
at the full diagnosis.

### D5 — Revalidation is event-driven and cheap, not a timer

The provider probes once on mount, then revalidates when the cached answer is older
than its TTL and the user navigates, and when a `revai:connection-stale` window event
fires — dispatched after saving engine settings, storing a credential, verifying a
provider, or starting/stopping local SonarQube. This mirrors the existing
`revai:ui-preferences` event contract. Because the endpoint is cached, a revalidation
after a config change is a cheap request that returns fresh data only when it must.

### D6 — SonarQube alerts only when it is enabled in the configuration

Local SonarQube is optional (`analyzers.sonarqube.enabled`). Docker stopped while
Sonar is disabled is the normal state for most users, so it is shown on
`/settings/connection` as informational and excluded from the banner verdict unless
enabled.

### D7 — Docs are TSX page components with catalog prose; commands are not translated

Chosen: one client component per page, prose in `docs.*` catalog keys, one registry
driving routes, sidebar and breadcrumb.

```
app/docs/layout.tsx          TopBar + sticky sidebar (mobile: <details> accordion)
app/docs/page.tsx            overview
app/docs/[slug]/page.tsx     looks the slug up in the registry; generateStaticParams

DOCS = [
  { slug: "getting-started",   group: "start" },
  { slug: "run-the-backend",   group: "start" },     ← banner / connection target
  { slug: "providers",         group: "start" },
  { slug: "first-review",      group: "review" },
  { slug: "findings-and-fix",  group: "review" },
  { slug: "sonarqube",         group: "review" },
  { slug: "cli-and-ci",        group: "advanced" },
  { slug: "agents-md",         group: "advanced" },
  { slug: "privacy-and-data",  group: "advanced" },
]
```

Slugs stay English so URLs are stable across locales; titles are catalog keys. One
registry feeds sidebar, params and breadcrumb, so they cannot drift.

Two consequences to respect:

- **Commands, product names and code blocks stay out of the catalog**, as TSX
  constants — exactly what `BackendUnreachable` already does with
  `COMPOSE_COMMANDS`. `i18n.test.ts` fails any entry whose pt-BR text equals en-US,
  so `"docker compose up -d"` as a catalog key would break the suite, and widening
  `SAME_IN_BOTH` with dozens of exceptions would corrode the test's value.
- **Docs keys live in separate catalog modules** (`lib/i18n/docs.en-US.ts`,
  `lib/i18n/docs.pt-BR.ts`) spread into the existing catalogs. `MessageKey` still
  covers them and the parity test still applies, without turning a 698-line catalog
  into a 2,000-line one.

Docs pages perform no data fetching, which is the requirement that matters: the page
explaining how to start the backend must render with the backend stopped, and with no
internet connection.

*Alternatives considered.* Markdown/MDX bundled per locale (needs a render
dependency, and duplicates the i18n mechanism the app already has); backend-served
Markdown (unavailable exactly when needed); links to GitHub (breaks offline use).

### D8 — Navigation: dedupe, then add

```
before  Projects  Insights  Data  Appearance  Settings▾(Engine, Skills&Prompts,
                                                       Appearance, Data)
after   Projects  Insights  Docs  Settings▾(Engine, API & AI, Skills & Prompts,
                                            Appearance, Data)
```

`Data` and `Appearance` are currently reachable twice; removing the top-level copies
makes room for `Docs` without growing the header. `SETTINGS_MENU` is the single
source for the dropdown and the settings breadcrumb, so `API & AI` is added there
once. The mobile `<details>` menu mirrors the same list.

The projects-screen chip (`ApiStatusBadge`) is deleted: it is the only consumer of
the component, the banner covers the failure case globally, and the detail moved to
`/settings/connection`. The `common.apiConnected` / `common.apiUnreachable` keys are
reused by the new screen rather than dropped.

## Risks / Trade-offs

- **Cached status can be up to 30 s stale** → the screen shows `checked_at` and a
  re-check button that sends `?refresh=true`; config-changing actions dispatch
  `revai:connection-stale`, so the stale window never covers a user action.
- **A cold `?refresh=true` costs a full CLI sweep (seconds)** → only ever triggered
  by an explicit user action, with a busy state on the button; the automatic paths
  always read the cache.
- **The banner adds a permanent band to the sticky header while a problem exists** →
  small height, one line, dismissible; nothing is rendered in the healthy state, so
  the cost is paid only by users who have something to fix.
- **Nine docs pages × two locales is real translation surface** (~120 keys) → scope
  is intentionally shallow per page at first, structure is registry-driven so pages
  can be added later, and the parity test fails the build if pt-BR falls behind.
- **Two screens can drift apart** (`/settings/connection` vs `ProviderPanel` on the
  engine page) → both read provider state from the same backend probe; connection
  shows the verdict plus scoreboard, engine keeps per-provider Test actions.
- **Debounce delays a true alert by a few seconds** → accepted deliberately; a
  warning that cries wolf on every backend restart is worse than one that arrives
  three seconds late.
- **`README.md` and the new docs can contradict each other** on how to start the
  backend → the same task list updates both, Docker Compose first, `uv run
  revai-api` as the development path.
