# Phase 8 — CLI Adapters

Implemented and verified on **2026-08-02**.

Phase 8 connects Claude Code, GitHub Copilot CLI, and Kiro CLI to the same
`Provider` protocol used by hosted APIs. The review pipeline does not branch on
transport: each adapter emits started, delta, usage, finished, or failed events and
the existing AI stage validates the resulting findings.

## Delivered

- Resolve the real executable path before every run, including Windows command
  shims.
- Execute fixed argument arrays with `shell=False`, closed standard input, a hard
  timeout, bounded error text, and worker-thread isolation for uvicorn on Windows.
- Drive Claude Code in print mode with JSON output, a validated JSON Schema,
  explicit model selection, no persisted session, no MCP configuration, and an
  empty tool set.
- Drive Copilot with its documented `-p --silent` scripting path, streaming
  disabled, custom repository instructions disabled, and no automatic tool grants.
- Parse both current plain silent output and JSONL envelopes emitted by other
  Copilot versions.
- Drive Kiro with `chat --no-interactive` and no trusted tools.
- Embed RevAI's findings schema into Copilot and Kiro prompts because those CLIs do
  not expose Claude's schema flag.
- Preserve Claude's reported session, tokens, cache reads, and cost; mark missing
  Copilot and Kiro accounting as estimated instead of claiming zero cost.
- Repair trailing commas in model JSON and retain valid findings when another item
  in the same batch fails schema validation.
- Expose all three adapters as ready in the API and Settings › Engine catalogue.

## Adapter Contracts

| Provider | Invocation | Authentication | Output and accounting |
|---|---|---|---|
| Claude Code | `claude -p … --output-format json --json-schema …` | `claude auth status` JSON, exit 0/1 | Validated envelope; session, tokens, cache, and cost when reported |
| Copilot CLI | `copilot -p … --silent --stream=off` | No non-billing status command; reported `unknown` | Plain assistant response, with JSONL fallback; usage estimated unless present |
| Kiro CLI | `kiro-cli chat --no-interactive …` | `kiro-cli whoami --format json` | Plain text through the tolerant extractor; usage estimated |

The command choices follow the vendors' current references:
[Claude Code CLI](https://code.claude.com/docs/en/cli-usage),
[Copilot CLI programmatic mode](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference),
and [Kiro headless mode](https://kiro.dev/docs/cli/headless/).

## Safety Boundaries

Prompts are individual process arguments, never shell source, so shell metacharacters
remain literal. RevAI does not grant Copilot or Kiro any tools. Claude receives an
empty tool list and a strict empty MCP configuration. Every process is killed and
reaped when `request_timeout_s` expires, including older or signed-out CLIs that
wait for interactive authentication despite a headless invocation.

The adapters receive only the filtered, changed-code chunks already prepared by the
deterministic pipeline. They never receive stored API credentials.

## Verification

Automated tests cover exact argument construction, schema injection, JSON and JSONL
parsing, old Copilot plain-output compatibility, Claude accounting, shell metacharacter
safety, timeouts, registry resolution, tolerant finding repair, and a complete Kiro
adapter-to-AI-stage flow. The subprocess runner is also exercised with the real
Python executable and a literal command-substitution string.

All three vendor CLIs were installed and exercised on the development machine:

- GitHub Copilot CLI 1.0.44 completed the real provider and finding-extraction flow
  with `{"findings": []}`.
- Claude Code 2.0.70 is an older installation whose auth probe and headless call
  both waited for interaction; RevAI terminated them at their configured ceilings
  and returned a retryable failure.
- Kiro CLI 2.16.0 was installed but signed out; its direct headless attempt was
  terminated at the test ceiling and returned a retryable failure.

The last two outcomes validate failure containment, not vendor authentication.
Deterministic adapter fixtures cover their successful response contracts without
requiring another account or secret.

```bash
cd platform/api
uv run pytest
uv run pytest -m cli -v
uv run ruff check revai tests

cd ../web
npm run typecheck
npm run lint
npm run build
npm run audit:prod
```
