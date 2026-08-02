# Phase 9 — Packaging, CLI, Containers, and CI

Implemented and verified on **2026-08-02**.

Phase 9 turns the source tree into repeatable local and container artifacts. It does
not change RevAI's trust boundary: the host install still binds to loopback, and the
optional Compose stack publishes both services on loopback only.

## Delivered

- A `revai` console command with:
  - `revai serve`, including a validated port override and an explicit no-reload mode;
  - `revai doctor`, which validates Python, data-directory access, YAML schemas, and
    POSIX credential permissions without probing a provider or spending a request;
  - `revai --version` and discoverable command help.
- Backward-compatible `revai-api` and `python -m revai` server entry points.
- Wheel and source-distribution builds with a smoke test that installs the wheel into
  a fresh virtual environment and runs the packaged doctor command.
- Digest-pinned Python 3.12.13 and Node 22.23.1 multi-stage Docker builds.
- Non-root API and web runtimes with dropped Linux capabilities, no-new-privileges,
  read-only root filesystems, bounded temporary filesystems, health checks, and
  loopback-only published ports.
- Next.js standalone output with explicit tracing and Turbopack roots, eliminating
  ambiguous parent-lockfile discovery.
- Separate browser and server-internal API addresses so SSR uses Compose DNS while
  the browser keeps the public loopback URL.
- A GitHub Actions pipeline for locked API tests, format/lint, web type/lint/build,
  production dependency audit, artifact installation, image builds, and a live
  Compose smoke test. Third-party actions are pinned to immutable commit SHAs.

## Local Installation

```bash
cd platform/api
uv build
uv tool install --force .
revai doctor
revai serve
```

The installed backend continues to store state under `~/.revai` unless
`REVAI_DATA_DIR` is set.

## Optional Container Stack

```bash
cd platform
docker compose up --build
```

- Web: <http://127.0.0.1:3000>
- API: <http://127.0.0.1:8799/api/health>
- Persistent state: the named `revai-data` volume

If either default port is occupied, set `REVAI_WEB_PORT` or `REVAI_API_PORT`.
When changing the API port, also set the browser-facing build address, for example:

```bash
REVAI_WEB_PORT=3100 REVAI_API_PORT=8899 \
NEXT_PUBLIC_API_URL=http://127.0.0.1:8899 docker compose up --build
```

The container is intentionally not given arbitrary access to the host filesystem.
Remote repositories can be cloned into the data volume. To open an existing local
repository, add an explicit read-only bind mount to the `api` service and select its
container path, for example:

```yaml
services:
  api:
    volumes:
      - /absolute/path/to/repositories:/workspace:ro
```

This opt-in mount keeps Compose from silently sharing a broad host directory.
Local CLI model adapters are host-install features; their vendor binaries and account
sessions are not copied into the API image.

## Reproducibility and Supply Chain

- Python dependencies are locked in `api/uv.lock`; CI uses `uv sync --frozen`, and
  Docker exports that same lock before building its runtime wheelhouse.
- JavaScript dependencies are locked in `web/package-lock.json`; CI and Docker use
  `npm ci`.
- Runtime base image tags include patch and distribution versions and are additionally
  pinned to their multi-platform image-index digest.
- GitHub Actions use full commit identifiers with their release versions documented
  in comments.
- CI and Docker pin uv 0.12.1, and the Python build backend pins Hatchling 1.31.0.
- Node 22.23.1 is pinned in `.nvmrc`; the package declares the actual Next.js minimum
  of Node 20.9.

## Verification

```bash
cd platform/api
uv run ruff check revai tests
uv run ruff format --check revai tests
uv run pytest
uv build

cd ../web
npm ci
npm run typecheck
npm run lint
npm run build
npm run audit:prod

cd ..
docker compose config --quiet
docker compose up --detach --build --wait
curl --fail http://127.0.0.1:8799/api/health
curl --fail http://127.0.0.1:3000/
docker compose down
```
