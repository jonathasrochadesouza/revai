# Contributing to revai

First off — thanks! revai is a small, focused project and every contribution
helps.

revai is an interactive AI code review agent skill. This is a dedicated skill
repo: `npx skills add <owner>/revai` installs exactly one skill from
`skills/revai/`.

## Project layout

```
skills/revai/
├── SKILL.md                 # agent-facing definition (keep under 100 lines)
├── scripts/revai.mjs        # diff + open-report CLI (Node >= 18, zero deps)
├── scripts/generate-review.mjs
├── templates/review.html    # self-contained interactive report (the "frontend")
└── references/              # schema, rubric, stack playbooks
```

## Getting started

1. Fork / clone the repo.
2. Node.js >= 18 and Git must be available (`node --version`).
3. Verify the install surface: `npx skills add . --list` must show exactly one
   skill (`revai`).
4. Manual E2E: run the 5-step flow from `skills/revai/SKILL.md` in an agent
   session against a real branch.

There is no build step and no package manager — scripts use Node built-ins
only. Please keep it that way.

## Commit messages (Conventional Commits)

Format: `<type>(<scope>): <subject>` — imperative mood, lowercase, no final
period. Reference issues in the footer: `Closes #N` auto-closes the issue when
the commit reaches `main`.

| Type     | When                                       |
| -------- | ------------------------------------------ |
| feat     | new feature                                |
| fix      | bug fix                                    |
| docs     | documentation only                         |
| refactor | no behavior change                         |
| style    | formatting only                            |
| test     | tests/validation only                      |
| chore    | repo maintenance, `.gitignore`, CI         |

Scopes map to what the commit touches. Keep **one scope per commit** and group
files by scope — don't mix `cli` and `report` files in one commit; split it
instead:

| Scope  | Files                                        |
| ------ | -------------------------------------------- |
| repo   | root files, `legacy/`, `.github/`            |
| cli    | `skills/revai/scripts/revai.mjs`             |
| report | `generate-review.mjs`, `templates/review.html` |
| docs   | `README.md`, `references/`, `CONTRIBUTING.md` |
| skill  | `skills/revai/SKILL.md`                      |

Examples:

```
feat(report): persist filter state (#8)
fix(cli): handle empty diff on detached HEAD (#21)
docs: document custom rules precedence
```

## Branches & PRs

- Branch naming: `<type>/<issue>-<slug>` (e.g. `feat/8-persist-filters`).
- Open an issue before a PR for anything larger than a typo fix.
- PR title follows the same conventional format; keep PRs small and scoped.

## Issue guidelines

- Check existing issues before opening a new one.
- One issue per concern; use the provided templates (`.github/ISSUE_TEMPLATE/`).
- For HTML report issues, include your Node version, OS, and browser.

## What we're looking for

Good starting points are labeled `good first issue` and `help wanted`.
Report-UI improvements (`templates/review.html`) are especially welcome — see
the `frontend` label.

## License

By contributing you agree that your contributions are licensed under the MIT
license of this project.
