# Phase 10 — Native Providers

Implemented and verified on **2026-08-02**.

Phase 10 connects Anthropic, OpenAI, Google Gemini, and Ollama directly to the same
streaming `Provider` protocol already used by OpenRouter and the three CLI agents.
The deterministic pipeline, finding schema, merge logic, persistence, exports, and
UI do not branch on the selected vendor.

## Delivered

- Anthropic Messages streaming with its versioned key header, separate system
  prompt, native JSON Schema output format, cache-read accounting, session IDs, and
  stop-reason enforcement.
- OpenAI Responses streaming with `store: false`, instructions, native strict
  structured output, cached-input accounting, response IDs, and explicit completion
  enforcement.
- Gemini `streamGenerateContent` over SSE with the API key in a header rather than
  the URL, system instructions, `responseJsonSchema`, usage metadata, prompt-block
  handling, and safely encoded model IDs.
- Ollama `/api/chat` over NDJSON with native schema formatting, local usage counts,
  output-limit handling, no credential field, and an exact zero-dollar cost.
- Concurrent health checks for all eight adapters. Hosted APIs use model-list
  endpoints that consume no model tokens; Ollama uses `/api/version`.
- Provider-aware custom base URLs. A saved override is applied only to the selected
  adapter and is cleared when the provider changes, so an OpenAI proxy can never be
  sent an Anthropic or Gemini request accidentally.
- Current curated model catalogues with custom-model escape hatches.
- Provider status and one-provider re-test actions for API and CLI engines in
  Settings › Engine.
- Ollama-aware budget enforcement, diff previews, and final review accounting.

## Wire Contracts

| Provider | Analysis endpoint | Structured output | Stream | Usage |
|---|---|---|---|---|
| Anthropic | `POST /v1/messages` | `output_config.format` JSON Schema | SSE Messages events | input, output, cache reads |
| OpenAI | `POST /v1/responses` | strict `text.format` JSON Schema | Responses SSE events | input, output, cached input |
| Gemini | `POST …:streamGenerateContent?alt=sse` | JSON MIME type + `responseJsonSchema` | SSE content candidates | prompt, candidate, cached content |
| Ollama | `POST /api/chat` | schema in `format` | NDJSON chat chunks | prompt/evaluation counts; $0 |

Sampling parameters are deliberately omitted from the current hosted-model requests.
Current Anthropic, OpenAI reasoning, and Gemini model families differ in which legacy
sampling controls they accept; deterministic structured output is more portable than
sending a parameter a vendor may reject. Ollama retains its local temperature option.

The request shapes follow the vendors' current primary references:
[Anthropic streaming](https://platform.claude.com/docs/en/build-with-claude/streaming),
[Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
[OpenAI Responses streaming](https://developers.openai.com/api/docs/guides/streaming-responses),
[OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[Gemini content generation](https://ai.google.dev/api/generate-content),
[Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output), and
[Ollama chat](https://docs.ollama.com/api/chat).

## Safety Boundaries

- Keys are held only in the existing credential store, placed in request headers,
  never query strings, and never returned by the API.
- Provider error messages are bounded and redact both the configured credential and
  common key formats before entering an event, log, browser, or persisted failure.
- A missing key performs no network request. Authentication, reachability, rate
  limits, bad requests, incomplete streams, safety blocks, and token-limit stops
  retain distinct states.
- `429` and server failures are retryable; ordinary client errors and content stops
  are not. This preserves the failure taxonomy needed by the deferred fallback
  design without silently switching models.
- Ollama defaults to loopback. A remote or proxied endpoint requires an explicit base
  URL override.

## Verification

The deterministic provider suite captures every outbound request with an
`httpx.MockTransport`, replays representative SSE or NDJSON responses, and compares
the same `{"findings":[]}` review through all four adapters. It also covers missing
keys without network access, zero-token health endpoints, Gemini's HTTP 400 invalid
key behavior, retryability, credential redaction, token/cache usage, registry
resolution, custom URL isolation, Ollama's free preflight, and zero-dollar diff
preview.

No paid provider request is required by the test suite. A real Ollama review is run
when a local service and pulled model are available; otherwise its deterministic wire
contract remains fully exercised without downloading a multi-gigabyte model.

On the implementation machine, Ollama 0.11.11 and the already-pulled `gemma3:12b`
completed the full AI stage: valid structured JSON, zero findings for harmless code,
147 input tokens, 6 output tokens, and an exact `$0.00` cost. Headless browser QA
then verified all five API choices, all eight health rows, Ollama's ready state and
absence of a key field, OpenAI's current model list and key field, provider-specific
base-URL placeholders, and an Ollama configuration save round-trip. No hosted model
call was made.

The complete backend run passed **245 tests** (with the explicitly opt-in live CLI
marker deselected). Ruff lint and format checks, TypeScript, ESLint, the production
Next.js build, and the production dependency audit all passed; the audit reported
zero vulnerabilities. Live startup validation also caught and fixed a misleading
CLI port log: `revai serve --port 8798` now reports the effective override rather
than the configured default.

```bash
cd platform/api
uv run ruff check revai tests
uv run ruff format --check revai tests
uv run pytest

cd ../web
npm run typecheck
npm run lint
npm run build
npm run audit:prod
```
