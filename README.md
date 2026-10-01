<div align="center">

<img src="logo.png" alt="revai logo" width="140"/>

# revai

**Interactive AI code review for git branches — packaged as an installable agent skill.**

Diff-only review · Interactive HTML report · Two-way fix loop

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Node.js ≥ 18](https://img.shields.io/badge/Node.js-%E2%89%A5%2018-339933?logo=node.js&logoColor=white)](https://nodejs.org)
[![GitHub Stars](https://img.shields.io/github/stars/jonathasrochadesouza/revai?style=flat&logo=github&labelColor=181717)](https://github.com/jonathasrochadesouza/revai/stargazers)
[![agent skills](https://img.shields.io/badge/agent%20skills-skills.sh-8A2BE2)](https://skills.sh)

[**Install**](#-install) · [**Usage**](#-usage) · [**Troubleshooting**](#-troubleshooting) · [**License**](#-license)

</div>

---

Interactive AI code review for git branches, packaged as an installable agent
skill. The agent reviews only the changed lines of your patch, writes
structured findings, generates a self-contained interactive HTML report
(Quality Gate, severity/file filters, skip/restore, dark/light theme), and
opens it in your browser automatically. A two-way fix loop closes the cycle:
fix items by ID through the agent, or click "Copy prompt" in the report and
paste it into any agent session.

## ✨ Features

- 🎯 **Diff-only review** — only the changed lines of your patch are reviewed,
  not the whole codebase.
- 📚 **Universal rubric + stack playbooks** — backend, frontend, mobile, data
  engineering, ML/data science, and games.
- 🧩 **Your rules win** — `.revai/rules.md` or `CODING_STANDARDS.md` overrides
  the built-in baseline.
- 📊 **Interactive HTML report** — Quality Gate, severity/file filters,
  skip/restore, dark/light theme — opened in your browser automatically.
- 🔁 **Two-way fix loop** — say *"fix CR-03"* to your agent, or click
  **Copy prompt** in the report and paste it into any agent session.
- 🪶 **Zero dependencies** — Node.js ≥ 18 built-ins only; no `npm install`.

## 📦 Install

From any agent that supports the [skills](https://skills.sh) ecosystem
(OpenCode, Claude Code, Codex, Cursor, 30+):

```bash
npx skills add jonathasrochadesouza/revai
```

- Project scope (default) — installs into the current project's agent skills
  directory (`.agents/skills/`, `.claude/skills/`, `.opencode/skills/`, …).
- Global scope — add `-g` to install for all projects.
- No symlink support (some Windows setups, network drives)? Use the documented
  fallback: `npx skills add jonathasrochadesouza/revai --copy` — the skill behaves
  identically either way.

## ✅ Requirements

- **Node.js ≥ 18** (the CLI scripts use built-ins only — no npm install needed)
- **Git** — the review target must be a git repository with a base branch
  (`origin/HEAD`, `main`, or `master`)

## 🚀 Usage

In any project, tell your agent:

> review this branch · run a code review · /revai

The agent drives five steps:

1. **Diff** — generates the review patch of the current branch or a branch you
   name, into `.revai/data/<slug>.patch`.
2. **Analyze** — reviews only the changed lines, using the universal rubric
   plus per-stack playbooks (backend, frontend, mobile, data engineering,
   ML/data science, games). Your project rules take precedence.
3. **Write findings** — persists `<slug>-review.json` and `<slug>-meta.json`.
4. **Generate + open** — validates the JSON and produces
   `.revai/reviews/<slug>-review.html`, then opens it in your browser.
5. **Fix loop** — choose items to fix:
   - *"fix CR-03"* — the agent applies the minimal fix, marks the finding
     resolved, and regenerates the report; the Quality Gate recalculates.
   - **Copy prompt** — copy a finding's prompt from the report and paste it
     into any agent session to apply the same fix.

Skipping findings is supported in the UI: skipped items stop blocking the
Quality Gate but are flagged as not best practice.

## 🙈 Consumer `.gitignore`

Review artifacts are local. Add this to your project's `.gitignore`:

```gitignore
.revai/
```

## 🧩 Custom rules

Optional. Place a `.revai/rules.md` (or `CODING_STANDARDS.md`) in your project
and the review will honor it: documented project standards override the built-in
baseline.

## 🩺 Troubleshooting

- **`Review data not found`** — run the diff step first, then write both JSON
  files (the agent does this; if it skipped a step, point it at
  `references/schema.md`).
- **Validation error naming a field** — the JSON files must follow the schema;
  fix the named field and regenerate. Nothing is written until validation
  passes.
- **Browser does not open** — headless/CI environments have no default browser;
  the report path is always printed. Open it manually.
- **`Branch ... does not exist` / empty diff** — check the branch name
  (`git branch -a`); a branch identical to the base branch has no diff.
- **`Cannot determine the base branch`** — the repo needs `origin/HEAD`,
  `main`, or `master`.
- **Symlink errors during install** — use the `--copy` fallback of the skills
  CLI.

## 📁 Repository layout

This repo is a dedicated skill repository — `npx skills add jonathasrochadesouza/revai`
installs exactly one skill:

```
skills/revai/
├── SKILL.md              # agent-facing skill definition
├── scripts/
│   ├── revai.mjs         # diff + open-report CLI
│   └── generate-review.mjs  # validate → inject → report
├── templates/
│   └── review.html       # interactive report template
└── references/
    ├── schema.md         # findings + meta JSON contract (V2)
    ├── rubric.md         # universal review baseline
    └── stack-playbooks.md # per-stack review playbooks
```

`legacy/` holds the deprecated PowerShell pipeline, kept for history only.

## 📄 License

MIT

This project is licensed under the [MIT License](LICENSE) — free to use,
modify, and distribute.

---

<div align="center">

**Made with ♥ by [Jonathas Rocha](https://github.com/jonathasrochadesouza)**

⭐ *Star the repo if revai helped your code ship safer.*

</div>
