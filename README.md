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

Kiro reviews require Kiro CLI 2.18 or newer. RevAI passes the configured model
explicitly and creates a temporary read-only agent with tools and MCP inheritance
disabled. SonarQube scans prefer Maven or Gradle, wait for server-side processing,
paginate issues and persist the actual quality-gate result.
