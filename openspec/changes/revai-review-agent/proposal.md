## Why

RevAI's reviews currently live inside RevAI: the web UI or the `revai` CLI runs
them, and the result is consumed there or exported. Users who work inside a
coding agent (Claude Code, Codex, Cursor, Gemini CLI, and everything else that
reads the AGENTS.md open standard) cannot carry RevAI's reviewer persona, rules,
finding contract, or report quality into that flow. The de-facto 2026 convention
for configuring project-scoped agent behaviour is a section in the project's
`AGENTS.md`; meanwhile RevAI already owns a strict findings JSON schema, a
prompt-injection guard, per-project rules, and a polished Paper-Light report
design — none of which a coding agent can reach today.

## What Changes

- Add a `revai agent` command group and `/api/agent/*` endpoints that
  **install** the RevAI reviewer into a user project: a managed, idempotent
  block between `<!-- revai:begin -->`/`<!-- revai:end -->` markers in the
  project's `AGENTS.md`, plus a copy of the standalone report template at
  `.revai/agent-report.html`. Exactly these two files are written, after an
  explicit user action; the first modification of an existing `AGENTS.md`
  leaves a `.revai-bak` backup.
- The managed block encodes: the RevAI reviewer persona (locale-aware), the
  prompt-injection guard, the compact findings JSON contract
  (`{"findings": [...]}`), a read-only permission boundary, and the render
  workflow. The configured engine (`provider_id`/`model`) is embedded as
  provenance only — API keys are never written into the project.
- Add the packaged template `revai/templates/agent-report.html`: a
  self-contained page (fixed vanilla renderer, no network dependency) with a
  single `__REVAI_DATA__` placeholder inside an
  `<script type="application/json">` node. Rendering a report = copy template
  to `<branch-slug>-revai.html` and replace the placeholder with the findings
  JSON, so the agent spends tokens on the JSON alone, never on markup.
- Add `revai agent render`, which validates the payload (full export envelope
  or compact agent envelope, against the strict `_FindingEnvelope` contract
  with a tolerant compact fallback) and writes the report. The agent does the
  copy+replace itself per the AGENTS.md instructions; the CLI path is the
  validation/convenience reference.
- Add Settings › Engine → "Review agent (AGENTS.md)" panel: project picker,
  AGENTS.md preview (merged document), install button, and an embedded sample
  report demo.
- The generated agent stays **read-only**: the only permitted writes are
  `revai-findings.json` and the report HTML; patches remain suggestions.

## Capabilities

### New Capabilities
- `agent-review`: the AGENTS.md managed block, installer, compact findings
  contract, and read-only permission model.

### Modified Capabilities
- None. No existing capability governs exports or agent behaviour.

## Impact

- **Backend** (`platform/api/revai`): new `agents/` module (generator,
  installer, renderer), new `templates/` package asset, new
  `api/routes/agent.py` router (registered in `main.py`), `cli.py` (new
  `agent` command group).
- **Frontend** (`platform/web/src`): `lib/api.ts` (agent types + client
  methods), `settings/engine/agent-panel.tsx` (new), `settings/engine/page.tsx`
  (mounts panel), i18n catalogs (`agent.*` keys) and the i18n parity test.
- **No persisted-schema change**: nothing is added to `~/.revai` documents and
  `SCHEMA_VERSION` is unchanged; the only artifacts live inside the user's
  project.
- **Security posture**: unchanged in RevAI itself (still never writes to a
  repo without confirmation); the *generated agent* is explicitly restricted
  to read-only review plus its two output artifacts.
