# Phase 0 — Skeleton

> **Status:** ✅ complete and verified · 2026-07-28

The goal of this phase was narrow on purpose: prove the two halves of the stack talk
to each other, and turn the **Paper Light** mock into real components — before any
review logic exists to hide problems behind.

---

## Run it

Two terminals.

```bash
# terminal 1 — backend
cd platform/api
uv sync --all-groups
uv run revai-api            # http://127.0.0.1:8799

# terminal 2 — frontend
cd platform/web
npm install
npm run dev                 # http://localhost:3000
```

Open <http://localhost:3000>. The header badge reads **API connected** when both are up.

API docs: <http://127.0.0.1:8799/api/docs>

---

## What was built

### Backend — `platform/api`

```text
revai/
├── main.py            application factory, CORS, lifespan
├── config.py          Settings + ~/.revai resolution
├── __main__.py        `python -m revai` / `revai-api`
└── api/routes/
    └── health.py      GET /api/health · GET /api/runtime
```

- **`create_app()` is a factory, not a module-level instance** — tests build an app
  with overridden settings instead of monkey-patching a global.
- **Every setting is `REVAI_`-overridable.** `data_dir` in particular, so tests never
  touch the real `~/.revai`.
- **`ensure_dirs()` runs on startup** and is idempotent, so no later phase has to
  check whether a directory exists.
- **Bound to `127.0.0.1`.** There is no authentication by design, so it must never be
  reachable from the network. CORS lists explicit loopback origins — never `*`.

### Frontend — `platform/web`

```text
src/
├── app/
│   ├── globals.css    the Paper Light design tokens
│   ├── layout.tsx     Geist + Geist Mono, metadata
│   └── page.tsx       live backend probe + token showcase
├── components/
│   ├── logo.tsx · top-bar.tsx
│   └── ui/badge.tsx · card.tsx
└── lib/api.ts         typed client + probeBackend()
```

- **Design tokens live in one place** (`globals.css`, Tailwind v4 `@theme`). The
  severity scale is defined once so no screen can invent its own colour mapping.
- **The page renders whether or not the API is up.** `probeBackend()` returns a
  discriminated union instead of throwing — when the backend is down the user is told
  exactly which commands to run. Both paths were verified in a browser.
- A dark variant will be a token remap later; no component changes required.

---

## Verification performed

| Check | Result |
|---|---|
| `uv run pytest` | **6 passed** |
| `uv run ruff check .` | **All checks passed** |
| `npm run typecheck` | clean |
| `npm run lint` | clean |
| `npm run build` | succeeded — `BUILD_ID` produced |
| `npm audit --omit=dev` | **0 vulnerabilities** |
| Browser · backend up | header shows **API connected**, live version/Python/data dir |
| Browser · backend down | header shows **API unreachable**, recovery instructions shown |
| Server logs | `GET /api/health 200` · `GET /api/runtime 200` |

Tests cover the health contract, the runtime payload, OpenAPI generation, and three
properties of the data directory: full tree creation, idempotency, and that the path
is always absolute.

---

## Decisions taken during implementation

### Port moved from 8787 to 8799

`8787` failed with `WinError 10013` — a socket permission error. Investigation showed
**another process was already listening on it** (a Java service on this machine), not
a Windows exclusion range. Rather than fight for the port, the default moved to
**8799**, verified free.

### Python pinned to 3.12

`uv` initially resolved **3.13.5** while the plan targets 3.12. A `.python-version`
file now pins it, so every machine and CI runner gets the same interpreter. The venv
was rebuilt on 3.12.10 and the full suite re-run.

### Uvicorn reload scope narrowed

`reload=True` was watching the **entire repository**, which meant editing a mock or a
markdown file restarted the API. It now watches only `revai/`.

### `npm audit fix --force` refused

The scaffold reported 12 high advisories. `npm audit fix --force` "resolves" them by
**downgrading Next.js from 16.2.12 to 9.3.3** — six major versions back, a far larger
risk than the advisories themselves.

Instead: `postcss` and `sharp` were pinned to patched releases via `overrides`,
clearing everything that reaches shipped code. The remaining advisories are all in the
**ESLint dev tooling** and cannot currently be fixed — verified empirically:

- The `brace-expansion` advisory covers **everything `<=5.0.7`**; only `5.0.8` is patched.
- The whole ESLint tree resolves `minimatch@3.1.5`, which requires `brace-expansion@^1.1.7`.
- `brace-expansion@5` changed to a named export, so forcing it throws a `TypeError`
  inside `minimatch@3`.
- The `maintenance-v1` line (`1.1.16`) is **not** patched — I reproduced the advisory
  PoC locally and it crashed with OOM.
- `eslint@10` (what `npm audit fix --force` suggests) is incompatible with
  `eslint-config-next@16` — attempted and reverted.

`npm audit --omit=dev` reports **zero** and is the release gate. The residual risk is
documented with exit criteria in `platform/web/SECURITY-NOTES.md`; the vulnerability
is only reachable through attacker-controlled glob patterns, and the only globs here
are hand-written in `eslint.config.mjs`.

---

## Not in this phase

No storage, no providers, no git, no pipeline, no reviews. Those are phases 1–7, and
the roadmap panel on the landing page tracks them.

**Next:** phase 1 — Pydantic domain models, YAML repositories with atomic writes and
file locking, and the Settings › Engine screen with its **Save to config.yaml** bar.
