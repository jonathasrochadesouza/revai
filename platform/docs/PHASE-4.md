# Phase 4 — Deterministic Pipeline

Implemented and verified on **2026-07-29**.

Phase 4 turns a Git diff into a persisted static-analysis review without calling
an AI provider. It is the deterministic half of RevAI's hybrid pipeline and the
input-preparation layer for Phase 5.

## Delivered

- Collect the full branch or working-tree diff without the browser's 1 MB
  transport limit.
- Filter binaries, lockfiles, generated output, vendored dependencies,
  minified assets, source maps, and snapshots.
- Parse unified diffs into exact added and removed line numbers with `unidiff`.
- Run enabled analyzers concurrently and isolate individual tool failures.
- Normalize Ruff, ESLint, Semgrep, and Gitleaks output into the shared
  `Finding` model.
- Exclude detected secret values from Gitleaks findings before persistence.
- Keep only findings that intersect added lines when `changed_lines_only` is
  enabled.
- Build context chunks at Python AST and offline Tree-sitter symbol boundaries.
- Enforce `max_context_tokens` while preparing chunks, without spending tokens.
- Materialize non-checked-out Git heads with `git archive`, leaving the user's
  branch and working tree untouched.
- Persist completed reviews under `~/.revai/reviews/<project>/<review>.yaml`.
- Render stages, analyzer status, metrics, and findings in the project inspector.

## Pipeline

```text
collect → filter → parse → static → chunk
```

| Stage | Output |
|---|---|
| `collect` | Full Git patch and changed-file statistics |
| `filter` | Reviewable source files plus a skipped-file count |
| `parse` | Hunks with exact source and target line numbers |
| `static` | Normalized findings from every available enabled analyzer |
| `chunk` | Symbol-aligned context bounded by the configured token ceiling |

Every Phase 4 review records `tokens_input = 0`, `tokens_output = 0`, and
`cost_usd = 0`. `estimated_context_tokens` describes the context prepared for a
future Phase 5 model call; it is not usage.

## Analyzer Behavior

| Analyzer | Discovery and execution |
|---|---|
| Ruff | RevAI's installed Python module; changed `.py` and `.pyi` files |
| ESLint | Project-local `node_modules/eslint/bin/eslint.js`; changed JS/TS files |
| Semgrep | Installed CLI plus a project `.semgrep.yml` or `.semgrep.yaml` |
| Gitleaks | Installed CLI, redacted JSON report stored outside the repository |
| Tree-sitter | Bundled offline grammars used for symbol-aware chunking |
| Built-in security | Dependency-free checks for dynamic execution, unsafe deserialization and shell injection primitives |
| Checkstyle | Reported unavailable until a project command is configured |

An enabled analyzer that is missing or not configured reports `unavailable`.
It does not fail the review. A tool that starts but exits unexpectedly reports
`failed`; other analyzers and the deterministic review still complete.

## Review modes

The review setup offers three user-selected modes: **Static only** runs enabled
analyzers without contacting a model; **AI-assisted** calls only the configured
model; and **Both** combines deterministic findings with the model's findings.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/projects/{id}/reviews/deterministic` | Run Phase 4 for a base/head pair |
| `GET` | `/api/projects/{id}/reviews` | List persisted reviews newest first |

The run response contains the persisted `Review`, five stage records, analyzer
records, and chunk metadata. Chunk source is not returned to the browser.

## Verification

The focused tests use real temporary Git repositories and the actual Ruff
executable. They cover noise filtering, exact changed lines, Python AST and
TypeScript Tree-sitter boundaries, token ceilings, analyzer normalization,
secret redaction, persisted zero-token accounting, large patches, review
history, unknown projects, and analysis of a non-checked-out branch without
switching the user's checkout.

Run verification with:

```bash
cd platform/api
uv run pytest
uv run ruff check revai tests

cd ../web
npm run typecheck
npm run lint
npm run build
```
