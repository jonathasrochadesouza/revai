## Context

RevAI is local-first: FastAPI on 127.0.0.1:8799 plus a Next.js web app, with
`~/.revai` as the single data home (config, credentials, rules). Reviews run
through a deterministic pipeline + an AI stage whose model output is strictly
validated against `_FindingEnvelope` (`pipeline/ai.py`). The HTML export
(`export/serializers.py::render_html`) is deliberately script-free. The CLI
(`revai.cli`) dispatches `serve`/`doctor`/`review`. OpenSpec changes are the
established way to propose cross-cutting work here.

Coding agents in 2026 converge on two conventions: the **AGENTS.md** open
standard (project-level instructions loaded by most coding agents) and
project-scoped **agent definitions** (e.g. `.claude/agents/*.md`,
`.kiro/agents/*.json`). The AGENTS.md route is tool-agnostic — one file, every
agent — and matches RevAI's local-first, no-lock-in posture.

## Goals / Non-Goals

**Goals:**
- Reuse RevAI's review quality (persona, rules, injection guard, strict
  findings contract, report design) inside any coding agent.
- Keep agent token cost proportional to findings, not markup: a fixed template
  with a data placeholder; the agent only produces the JSON.
- Preserve RevAI's read-only posture: explicit install, managed block,
  backup, and a permission section that constrains the generated agent.

**Non-Goals:**
- Not writing `.claude/agents/`, `.kiro/agents/`, or Copilot instructions
  (a natural follow-up; the generator is built to allow more templates later).
- Not making RevAI's own pipeline agentic (tool-loop for API providers) —
  deferred until adoption justifies it.
- Not letting the generated agent apply fixes, commit, or push.
- Not posting findings to GitHub/GitLab PRs (still export-only).

## Decisions

- **AGENTS.md managed block, not a separate file.** One standard, idempotent
  regeneration via `revai:begin`/`revai:end` markers; user content above the
  block is preserved and backed up once (`AGENTS.md.revai-bak`).
- **Template with a JSON placeholder instead of server-side HTML rendering.**
  The template ships in the wheel and is copied into the project; the agent's
  render step is a plain copy + replace, requiring nothing but the project
  files. The template carries a small fixed vanilla renderer (the one place
  RevAI's report has JavaScript — audited, offline, no remote assets).
- **Two accepted payload shapes.** The full export envelope
  (`{format_version, project, review}`) and the compact agent envelope
  (`{"findings": [...]}`) both validate; strict-first, tolerant-compact
  fallback. `</` is escaped to `<\/` in the injected JSON so a finding body
  can never terminate the JSON script node.
- **Provenance, not credentials.** The block embeds
  `provider_id/model` as a comment so users know what generated it; keys stay
  in `~/.revai/credentials.yaml`.
- **CLI asks before writing; API applies only on POST.** `revai agent install`
  prompts when interactive, requires `--yes` when piped, and `--dry-run`
  prints the merged document. The web panel previews the merged document
  before the apply click.

## Risks / Trade-offs

- A report page with JavaScript diverges from the script-free `render_html`
  export. Accepted for the agent report only: the renderer is fixed and
  offline; the classic export remains script-free.
- An agent following the block could still ignore the read-only rules —
  the AGENTS.md is an instruction contract, not a sandbox. Mitigated by the
  explicit permission section and by RevAI itself never gaining write access.
- Template drift vs. the web design. Accepted: the template ports the Paper
  Light tokens by hand; a snapshot test locks its structure.

## Migration Plan

Additive only: new module, new router, new command group, new panel. No
persisted document changes, so no migration is needed. Rollback is removing
the managed block from an `AGENTS.md` (or restoring the backup).
