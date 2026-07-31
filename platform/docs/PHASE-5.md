# Phase 5 — AI Review Stage

Implemented and verified on **2026-07-30**.

Phase 5 completes RevAI's hybrid review loop. The deterministic pipeline still
runs first; only its filtered, symbol-aligned changed-code chunks are sent to the
configured provider. Provider output is streamed to the browser, validated
against RevAI's finding contract, merged with analyzer findings, and persisted.

## Delivered

- Stream a complete review over Server-Sent Events (SSE).
- Report the five deterministic stages plus `ai` and `merge`.
- Emit analyzer, provider, cumulative output, usage, completion, and failure
  events as they happen.
- Request strict structured JSON from providers that support schemas.
- Tolerate one Markdown code fence while still enforcing a strict Pydantic
  finding envelope.
- Reject AI findings whose file or line was not included in model context.
- Prepare every distinct changed symbol in a Git hunk, not only its first line.
- Enforce configured context and spend ceilings before calling the provider.
- Merge deterministic and AI findings with confidence-aware deduplication.
- Persist provider/model, token counts, cached tokens, actual or estimated cost,
  duration, and terminal status.
- Abort the backend task when the browser cancels or disconnects.
- Render a responsive seven-stage progress view, event stream, usage metrics,
  analyzer status, and combined findings.

## Pipeline

```text
collect → filter → parse → static → chunk → ai → merge
```

| Stage | Output |
|---|---|
| `collect` | Full Git patch and changed-file statistics |
| `filter` | Reviewable source files and skipped-file count |
| `parse` | Exact added and removed line numbers |
| `static` | Normalized local analyzer findings |
| `chunk` | Distinct changed-symbol contexts within the token ceiling |
| `ai` | Validated, in-context AI findings and usage |
| `merge` | Ranked and optionally deduplicated combined findings |

## Stream API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/projects/{id}/reviews/stream` | Run the full hybrid review |
| `POST` | `/api/projects/{id}/reviews/deterministic` | Keep the zero-token Phase 4 path |
| `GET` | `/api/projects/{id}/reviews` | List persisted reviews newest first |

Start a review with:

```bash
curl -N -X POST http://127.0.0.1:8799/api/projects/PROJECT_ID/reviews/stream \
  -H "Content-Type: application/json" \
  -d '{"base":"main","head":"feature/auth"}'
```

Each SSE message has one JSON object in its `data` field:

```text
data: {"type":"review_started"}

data: {"type":"stage","name":"collect","status":"completed","duration_ms":18,"detail":"3 changed files."}

data: {"type":"provider","model":"anthropic/claude-sonnet-4"}

data: {"type":"delta","characters":384}

data: {"type":"usage","input_tokens":1420,"output_tokens":286,"cached_tokens":0,"cost_usd":0.0081,"is_estimated":false}

data: {"type":"completed","result":{"review":{"status":"completed"},"stages":[],"analyzers":[],"chunks":[]}}
```

The complete event vocabulary is:

| Event | Meaning |
|---|---|
| `review_started` | The stream worker has started |
| `stage` | A pipeline stage completed |
| `analyzer` | One local analyzer completed, failed, or was unavailable |
| `provider` | The provider accepted the request and selected a model |
| `delta` | Cumulative response characters received |
| `usage` | Input, output, cached tokens, and cost |
| `completed` | Persisted review plus stage, analyzer, and chunk metadata |
| `failed` | Terminal error message; a started review is persisted as failed |

## Safety And Accounting

The preflight guard rejects a call when prepared context exceeds
`max_context_tokens` or its estimated input cost exceeds
`max_spend_usd`. No provider request is made in either case.

The model receives only changed-code chunks produced after noise filtering.
Every returned finding must validate against the severity, category, location,
confidence, and optional patch schema. RevAI then discards locations outside the
supplied chunks. This prevents an otherwise valid response from attaching an
invented finding to unseen code.

Provider-reported cost is stored when available. Otherwise RevAI stores an input
estimate and sets `cost_is_estimated = true`; the UI does not present a guess as
an exact charge.

## Browser Behavior

The typed client parses SSE across arbitrary network chunk boundaries. Consecutive
model deltas are coalesced in React state while preserving their cumulative
character count. The run button becomes a cancel action during a review, and an
`AbortController` closes the connection when cancelled or when the inspector
unmounts.

## Verification

Focused tests cover fenced structured output, schema rejection, in-context
finding validation, confidence-aware merge, spend preflight, provider events and
usage, multi-symbol chunking, seven streamed stages, combined persistence, and
review history.

```bash
cd platform/api
uv run pytest
uv run ruff check revai tests

cd ../web
npm run typecheck
npm run lint
npm run build
```
