## ADDED Requirements

### Requirement: Managed AGENTS.md install
The system SHALL provide an install action that writes a single managed block
into the target project's `AGENTS.md`, delimited by
`<!-- revai:begin (managed block — edit in RevAI, not here) -->` and
`<!-- revai:end -->`, containing the RevAI reviewer persona, the
prompt-injection guard, the compact findings JSON contract, the render
workflow, and the read-only permission section. Regeneration SHALL be
idempotent: re-installing replaces the existing managed block in place and
preserves all content outside it. The first modification of an existing
`AGENTS.md` SHALL leave the original as `AGENTS.md.revai-bak`.

#### Scenario: Fresh install creates AGENTS.md and template
- **WHEN** a user runs `revai agent install <project> --yes` on a project
  without `AGENTS.md`
- **THEN** the project contains an `AGENTS.md` whose content is exactly the
  managed block, and `.revai/agent-report.html` containing the packaged
  template

#### Scenario: Install into an existing AGENTS.md preserves user content
- **WHEN** a user installs into a project whose `AGENTS.md` already has
  unrelated content and no managed block
- **THEN** the file contains the original content followed by the managed
  block, a `AGENTS.md.revai-bak` with the original content exists, and the
  managed block appears exactly once

#### Scenario: Re-install is idempotent
- **WHEN** a user installs twice into the same project
- **THEN** the second run leaves `AGENTS.md` byte-identical to the first
  run's result (no duplicate block) and creates no second backup

#### Scenario: Dry run writes nothing
- **WHEN** a user runs the install command with `--dry-run`
- **THEN** the merged document is printed and no file in the project is
  created or modified

### Requirement: Read-only permission boundary
The managed block SHALL instruct the agent to remain read-only: the only
permitted writes are `revai-findings.json` and the report HTML; no tracked
file may be modified; no commit, push, or write command may be run; and
`suggested_patch` values are suggestions for the human, never applied.

#### Scenario: Clean review is valid
- **WHEN** the agent finds no issues
- **THEN** it writes `{"findings": []}` and renders the report with an empty
  findings list instead of omitting the report

### Requirement: No credentials in the project
The managed block and every generated artifact SHALL NOT contain API keys,
tokens, or any content of `credentials.yaml`. The configured
`provider_id`/`model` may appear as provenance only.

#### Scenario: Provenance comment names the engine
- **WHEN** the block is generated for engine `openrouter` and model
  `anthropic/claude-sonnet-5`
- **THEN** the block contains that provider/model pair in a comment and no
  secret material anywhere in the block

### Requirement: Findings JSON contract
The agent SHALL produce exactly one JSON object with a `findings` array whose
items match the RevAI finding contract (severity, category, title,
description, file, line_start, optional line_end/rule_id/confidence/
suggested_patch). Renderers SHALL accept both the compact envelope
(`{"findings": [...]}`) and the full export envelope
(`{format_version, project, review}`) and SHALL reject anything else.

#### Scenario: Compact envelope renders
- **WHEN** the payload is `{"findings": [{"title": "x", "file": "a.py",
  "line_start": 3}]}`
- **THEN** validation passes and the report renders the finding with default
  severity/category/source decorations

#### Scenario: Invalid payload is rejected before writing
- **WHEN** `revai agent render` receives a payload without a `findings` array
  or with malformed findings
- **THEN** the command exits non-zero, prints a structured failure, and
  writes no report file

### Requirement: Standalone report template
RevAI SHALL ship a single self-contained HTML template with one data
placeholder inside an `application/json` script node and a fixed vanilla
renderer (severity metrics, findings cards, filters, patch details, graceful
error and empty states). Injected JSON SHALL be escaped so that finding text
cannot terminate the JSON script node. The report MUST work offline with no
remote assets.

#### Scenario: Injection escapes script-terminating sequences
- **WHEN** a finding description contains `</script>`
- **THEN** the injected JSON escapes the sequence and the renderer receives
  the description unchanged after JSON parsing

#### Scenario: Report naming follows the branch slug
- **WHEN** a review for branch `feat-user` is rendered
- **THEN** the report file is named `feat-user-revai.html`

#### Scenario: Broken payload shows an error card, not a blank page
- **WHEN** the JSON inside the placeholder is not valid or does not match the
  contract
- **THEN** the page renders a styled error card describing the failure
