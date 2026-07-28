# RevAI API

FastAPI backend for the RevAI Platform. Local-first, single-user, no authentication —
it binds to `127.0.0.1` on purpose and must never be exposed to a network.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Getting started

```bash
uv sync --all-groups     # install runtime + dev dependencies
uv run revai-api         # start on http://127.0.0.1:8799
```

Interactive docs: <http://127.0.0.1:8799/api/docs>

## Development

```bash
uv run pytest            # tests
uv run ruff check .      # lint
uv run ruff format .     # format
```

## Configuration

Every setting is overridable with a `REVAI_` prefixed environment variable, or via a
`.env` file — see `.env.example`.

| Variable | Default | Purpose |
|---|---|---|
| `REVAI_HOST` | `127.0.0.1` | Bind address |
| `REVAI_PORT` | `8799` | Bind port |
| `REVAI_DATA_DIR` | `~/.revai` | Where projects, reviews and config live |
| `REVAI_ENVIRONMENT` | `development` | Enables auto-reload when `development` |

## Layout

```
revai/
├── main.py          application factory
├── config.py        settings + data directory resolution
├── api/routes/      HTTP endpoints
├── domain/          Pydantic models (phase 1)
├── storage/         YAML repositories (phase 1)
├── providers/       OpenRouter, then CLIs (phase 2)
├── pipeline/        review stages (phases 4–5)
├── analyzers/       linters and AST tooling (phase 4)
└── export/          JSON · Markdown · HTML (phase 7)
```

Current phase: **0 — skeleton**. Only `/api/health` and `/api/runtime` are implemented.
See `../docs/ARCHITECTURE.md` for the full plan.
