# RevAI

Local-first AI code review for Git repositories. Repositories stay on your machine;
only the filtered diff context required for a review reaches the model provider you
configure. RevAI has no account, telemetry, or hosted project storage.

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
