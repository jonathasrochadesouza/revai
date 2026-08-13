# RevAI API

FastAPI backend for the RevAI Platform. Local-first, single-user, no authentication —
it binds to `127.0.0.1` on purpose and must never be exposed to a network.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Getting started

```bash
uv sync --all-groups     # install runtime + dev dependencies
uv run revai doctor      # validate Python, storage, config and credential permissions
uv run revai serve       # start on http://127.0.0.1:8799
```

`revai-api` and `python -m revai` remain compatible aliases for the server.

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
| `REVAI_KIRO_CLI_PATH` | _(PATH lookup)_ | Absolute Kiro CLI path, for services whose PATH does not include it |
| `SONAR_TOKEN` | _(none)_ | SonarQube token; never persisted in `config.yaml` |

`revai review` provides a headless CI contract with JSON, Markdown, HTML and SARIF
output. Run `revai review --help` for scopes, provider/model overrides and threshold
exit codes. Project quality commands are stored as argument arrays and executed with
`shell=False`.

## Layout

```
revai/
├── main.py          application factory
├── config.py        settings + data directory resolution
├── api/routes/      HTTP endpoints
├── domain/          Pydantic models (phase 1)
├── storage/         YAML repositories (phase 1)
├── providers/       hosted APIs, Ollama and local CLIs (phases 2, 8, 10)
├── git/             repository metadata, trees and diff previews (phase 3)
├── pipeline/        review stages (phases 4–5)
├── analyzers/       linters and AST tooling (phase 4)
└── export/          JSON · Markdown · HTML (phase 7)
```

Current phase: **10 — native providers**. Anthropic, OpenAI, Gemini, and Ollama now
implement the same provider protocol as OpenRouter and the local CLI adapters. See
[`../docs/PHASE-10.md`](../docs/PHASE-10.md).
