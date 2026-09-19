# RevAI

Local-first AI code review for Git repositories. Repositories stay on your machine;
only the filtered, secret-redacted context required for a review reaches the model
provider you configure. Repository content is treated as untrusted prompt data.
RevAI has no account, telemetry, or hosted project storage.

## Run locally

Start the API in one terminal:

```bash
cd platform/api
uv sync --all-groups
uv run revai-api
```

Then start the web app in another:

```bash
cd platform/web
npm install
npm run dev
```

Open `http://localhost:3000`. The local API listens on `http://127.0.0.1:8799`.

## First review

1. Open **Settings → Engine**, choose an implemented provider, store a key, and verify it.
2. Open a local Git folder or clone a repository from the Projects screen.
3. Check the diff preview and its token/cost estimate, then run the review.
4. Review findings, copy a suggested patch when present, and mark items fixed, dismissed, or false positive.

Reviews, configuration, and masked credentials metadata live under `~/.revai/`.
Credentials are stored separately from repositories. Review cost is estimated before
execution, confirmed when it exceeds your warning threshold, and blocked when it
exceeds the configured hard budget.

## Headless and CI review

The installed CLI runs the same read-only pipeline without a web server and supports
branch, selected-file and whole-project scopes. Exit code `1` means the configured
finding threshold was reached; execution/configuration errors return `2`.

```bash
revai review . --base main --head feature/payments \
  --mode both --model claude-haiku-4.5 \
  --format sarif --output revai.sarif --fail-on medium
```

Available report formats are JSON, Markdown, standalone HTML and SARIF 2.1.0.

## Applying a fix

A finding's suggested patch can be applied to the working tree — always
unstaged, never committed by RevAI. The fix service refuses to run when the
active branch differs from the review head or the target file changed since the
review (recorded content hash), validates the patch with `git apply --check`
first, and re-runs the analyzer that produced the finding after applying; if
the rule still fires the change is reverted and nothing is left behind.
`--dry-run` validates and prints the patch without touching the tree.

```bash
revai fix . --review <review-id> --finding <finding-id> --dry-run
revai fix . --review <review-id> --finding <finding-id>
revai fix . --review <review-id> --finding <finding-id> --generate  # model-generated fix
```

Exit code `0` means applied (or a valid dry run); `1` means the fix could not
be applied (stale, branch mismatch, failed re-validation); `2` is a
configuration or execution error. In the web app the same flow lives on each
finding card: preview the diff, apply to the working tree, then review with
`git diff` before committing. When a finding has no patch, `Generate fix`
asks the configured model for a minimal search/replace edit, converts it to a
real diff, and applies it through the same validation pipeline.

Kiro reviews require Kiro CLI 2.18 or newer. RevAI passes the configured model
explicitly and creates a temporary read-only agent with tools and MCP inheritance
disabled. SonarQube scans prefer Maven or Gradle, wait for server-side processing,
paginate issues and persist the actual quality-gate result.

## Review agent (AGENTS.md)

RevAI can install its reviewer into any coding agent that reads `AGENTS.md`
(Codex, Cursor, Gemini CLI, opencode, and others). The install writes exactly two
files in your project, after your confirmation:

- `AGENTS.md` — a managed block between `revai:begin`/`revai:end` markers with
  the RevAI reviewer persona, your project rules from `~/.revai/rules/`, the
  findings JSON contract, and a strict read-only permission section. Your own
  content in the file is preserved; the first install leaves a backup.
- `.revai/agent-report.html` — the standalone report template.

After reviewing, the agent writes only `revai-findings.json` (compact findings
JSON — that is the entire token cost) and renders the report by copying the
template to `<branch-slug>-revai.html` (e.g. `feat-user-revai.html`) and replacing
its single `__REVAI_DATA__` placeholder with the JSON. Open the file in a browser:
a RevAI-quality report, offline, with metrics, filters and suggested patches.

```bash
revai agent install . --dry-run     # print the merged AGENTS.md
revai agent install . --yes         # write AGENTS.md + template
revai agent render revai-findings.json --name feat-user   # validated render
```

The agent is instructed never to modify tracked files, commit, or push, and to
treat patches as suggestions. API keys never leave `~/.revai/credentials.yaml`.
You can also install and preview the report from **Settings → Engine → Review
agent**.
