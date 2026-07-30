# Phase 3 — Projects and Git

Implemented and verified on **2026-07-29**.

Phase 3 turns the configured platform into a repository workspace. RevAI can now
remember local repositories, clone remotes into a selected local folder, inspect
branches and tracked files, and preview changes without modifying source.

## Delivered

- Open any folder inside a local Git worktree; RevAI resolves and persists the root.
- Browse with the native folder picker and capture the selected absolute path.
- Deduplicate projects by resolved repository path.
- Clone Git-supported remotes under a folder selected by the user.
- Detect the current and base branch, preferring `main`, `develop`, then `master`.
- Detect languages from tracked file extensions.
- List tracked files at a selected Git ref.
- Preview `base...head`, or tracked and untracked working-tree changes when base
  and head match.
- Report changed files, additions, deletions, binary files, estimated input tokens,
  and estimated input cost.
- Cap the transported patch at 1 MB and report truncation without changing Git state.
- Render repository entry, search/filtering, branch controls, file tree, estimates,
  and a color-coded unified diff in the Paper Light workspace.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/projects` | List persisted projects with live branch metadata |
| `POST` | `/api/projects/pick-folder` | Open the native folder picker |
| `POST` | `/api/projects/open` | Open or reuse a local repository |
| `POST` | `/api/projects/clone` | Clone into a selected destination folder |
| `GET` | `/api/projects/{id}` | Read one project |
| `GET` | `/api/projects/{id}/tree?ref=HEAD` | List tracked files |
| `GET` | `/api/projects/{id}/diff?base=main&head=feature` | Preview changes |

All Git commands use argument arrays, never a shell. Read operations have a
30-second timeout; clone has a 120-second timeout. Failed clones remove only the
new destination created for that attempt.

## Estimates

The preview uses a deliberately simple, visible estimate:

```text
estimated_tokens = ceil(unified_diff_characters / 4)
estimated_cost_usd = estimated_tokens × $3 / 1,000,000
```

This is an input-only planning estimate, not provider billing. Phase 5 replaces the
fixed rate with provider/model telemetry while preserving the `estimated` label.

## Verification

The backend tests create real temporary Git repositories and cover metadata
detection, path deduplication, validation, tracked-file listing, branch and
working-tree diffs, estimates, selected-folder cloning, unknown refs, and OpenAPI
routes.

The browser flow was also run against the RevAI repository itself: it opened the
repository, listed 97 tracked files, and rendered the live six-file working-tree
diff. Desktop (`1440 × 1000`) and mobile (`390 × 844`) layouts were checked.

Run verification with:

```bash
cd platform/api
uv run pytest
uv run ruff check revai tests

cd ../web
npm run typecheck
npm run lint
npm run build
```
