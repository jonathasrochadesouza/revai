# Contributing to RevAI

Thanks for your interest in contributing! RevAI is a local-first AI code review
platform: FastAPI backend, Next.js web UI, and a `revai` CLI — all designed to
run on your machine, store data as plain YAML, and never send code anywhere
except the AI provider you configure.

## Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 22+ (see `platform/web/.nvmrc`) with npm
- Git

## Development setup

```bash
# Backend
cd platform/api
uv sync --all-groups
uv run revai serve            # API on http://127.0.0.1:8799

# Web (second terminal)
cd platform/web
npm ci
npm run dev                   # http://localhost:3000 (falls back to 3001 if taken)
```

## Quality gates

Every pull request runs the same checks as `main`; run them locally first:

```bash
# platform/api
uv run ruff check revai tests
uv run ruff format --check revai tests
uv run pytest --cov --cov-fail-under=75     # full suite with coverage gate
uv run pytest -m cli                        # slow, shells out to real CLIs

# platform/web
npm run typecheck
npm run lint
npm run test:coverage
npm run build
```

Conventions the codebase holds itself to (a review tool holds itself to the
standard it enforces):

- **No TODO/FIXME comments.** If something is deferred, document it in
  `platform/docs/` (see `DEFERRED-FALLBACK-PROVIDER.md` for the expected style)
  or open an issue.
- **Errors are structured, never prose.** Backend errors must carry a
  `error_key` + `params` (see `platform/api/revai/errors.py`); every user-facing
  key must have en-US and pt-BR entries in `platform/web/src/lib/errors.ts`.
  New keys are added in **both** locales — the i18n tests enforce parity.
- **Every persisted document has a `schema_version`.** Changing a persisted
  shape means bumping `SCHEMA_VERSION` in `platform/api/revai/domain/enums.py`
  and registering an upgrade step in
  `platform/api/revai/storage/migrations.py` with a test.
- **Comments explain why, not what.** The codebase is comment-rich on intent
  and constraints; match that style.

## Architecture and decisions

Read `platform/docs/ARCHITECTURE.md` first — it records the approved plan and
locked decisions (YAML persistence, no auth by design, hybrid pipeline). Phase
docs (`PHASE-*.md`) describe each increment. For larger changes, follow the
OpenSpec workflow in `openspec/`.

## Releases (maintainers)

Releases are tag-driven and fully automated:

1. Update `revai/__init__.py` `__version__` (single source of truth — hatchling
   reads it at build time) and mirror it in `platform/web/package.json`.
2. Add a `CHANGELOG.md` entry describing user-visible changes.
3. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. The `release` workflow builds the wheel/sdist, creates a GitHub Release with
   the artifacts, and publishes to PyPI via
   [trusted publishing](https://docs.pypi.org/trusted-publishers/) — no token
   in secrets. First-time setup: configure the `pypi` trusted publisher for
   this repository (workflow `release.yml`) on PyPI, then tags publish
   automatically.

## Reporting issues

Open a GitHub issue with the `revai doctor --json` output and the failing
step. For security concerns, see `SECURITY.md` — do not open a public issue.
