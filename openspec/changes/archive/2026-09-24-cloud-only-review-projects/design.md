## Context

RevAI's `Project` model (`domain/models.py`) always carries a `path: str` that
points at a persistent local Git working tree. Every read path assumes it:
`run_deterministic_pipeline` (`pipeline/runner.py`) does `Path(project.path)`
immediately; `diff_preview`/`snapshot_preview`/`materialized_tree`/`apply_patch`
(`git/repo.py`) all take that path as their `cwd`. The two existing creation
flows, `open_project` and `clone_project` (`api/routes/projects.py`), both end
by writing a `Project` whose `path` is a real, permanent directory.

`materialized_tree()` already extracts a ref into a `tempfile.TemporaryDirectory`
for static analysis, and it self-deletes on context exit — this is the pattern
the ephemeral-clone project kind extends one level up: the *whole repository*,
not just one ref, lives in a temp directory for the duration of one review run.

## Goals / Non-Goals

**Goals:**
- Add a `kind` discriminator to `Project` (`LOCAL_OPEN`, `LOCAL_CLONE`, `CLOUD`)
  so storage, API responses, and UI can branch on it without inferring from
  nullable fields.
- For `CLOUD` projects, `path` is `None` at rest; a working directory is
  materialized only for the duration of a single review run and removed
  afterward unconditionally (success, failure, exception, or cancellation).
- Reuse `diff_preview`, `materialized_tree`, `run_analyzers`, and the AI stage
  completely unmodified — they operate on whatever `Path` they are given today
  and do not need to know a project is cloud-backed.
- Reject fix/apply requests for `CLOUD` projects with a specific, user-actionable
  error rather than a generic 404/500.
- Surface project kind in the UI (cloud/globe badge) without changing the shape
  of unrelated project fields.

**Non-Goals:**
- No GitHub/GitLab/Bitbucket REST API integration. Cloud projects clone over
  plain `git` (SSH or HTTPS+PAT-as-password), same transport as `clone_repository`
  uses today.
- No fix/apply support for cloud projects in this change.
- No concurrent/parallel review support for the same cloud project — the
  existing single-run-per-project assumption (`ReviewLimiter`) is unchanged.
- No change to how local-open or local-clone projects behave.

## Decisions

### 1. `Project.kind` discriminator + nullable `path`

Add `class ProjectKind(StrEnum): LOCAL_OPEN / LOCAL_CLONE / CLOUD` to
`domain/enums.py` (bumps `SCHEMA_VERSION`, needs a migration step like the
existing v1→v5 ones in `storage/migrations.py`: default `kind` to `LOCAL_CLONE`
if `remote_url` is set else `LOCAL_OPEN` for pre-existing documents).
`Project.path` becomes `str | None`; every current call site that does
`Path(project.path)` must go through a helper that raises a clear
`GitError`-style error if `path` is `None` outside of an active review run —
this makes "cloud project with no live working dir" a first-class, named error
state instead of a crash.

Alternative considered: keep `path` required and set it to a sentinel (e.g.
empty string). Rejected — sentinels are exactly the kind of ambiguity the
existing `BudgetConfig` docstring already warns against (`None` vs `0`), and a
missing `Path` should fail loudly, not resolve to `Path("")` (cwd).

### 2. Ephemeral clone lives in the review run, not in `Project`

`Project` for a cloud kind stores `remote_url` (required) and `base_branch`
(same field, still required) — nothing else changes shape. The ephemeral
checkout is scoped to a single review execution: a new context manager
`ephemeral_clone(remote: str) -> Iterator[Path]` in `git/repo.py`, sibling to
`materialized_tree`, using `tempfile.TemporaryDirectory(prefix="revai-cloud-")`
and `git clone -- <remote> <tempdir>` (no `--depth`, so `base..head` diffing
and `detect_base_branch` keep working exactly like `clone_repository` today;
shallow clones break `git diff base..head` when base isn't in the shallow
history).

`run_deterministic_pipeline` and the AI review route gain one branch: if
`project.kind is ProjectKind.CLOUD`, wrap the existing body in
`with ephemeral_clone(project.remote_url) as repository:` instead of
`repository = Path(project.path)`. Every line after that is unchanged — this
is the reuse the exploration identified as the main win.

Alternative considered: give the cloud project a `path` that's set only during
the run and cleared after (mutating `Project` in place). Rejected — persisting
a run-scoped filesystem path on a document that's serialized to YAML risks a
crash mid-review leaving a stale path pointing at a directory that no longer
exists, and callers would still need to special-case "is this path currently
valid" instead of the cleaner "does this project have a kind that never had
one." Keeping the temp path purely local to the execution's stack frame means
crash-safety is automatic — nothing durable to go stale.

### 3. Cleanup guarantee

`tempfile.TemporaryDirectory` as a context manager already deletes on any
exit path, including exceptions — this covers "review fails" and "review
throws." Cancellation (`cancel_review` in `api/routes/reviews.py`) needs the
same context manager to still be active on the task that's cancelled (i.e.
the clone/review must run inside the same `asyncio` task whose cancellation
tears down the `with` block), not detached into a fire-and-forget job — this
is consistent with how deterministic pipeline stages already run today.

### 4. Fix/apply rejection

`fixes/service.py::apply_finding_fix` and `api/routes/fixes.py` gain an early
check: if the finding's project `kind is ProjectKind.CLOUD`, raise/return a
distinct error (`fix.unavailable_for_cloud_project`) before any patch or
git-apply logic runs. The web app's finding card checks the same project kind
(already loaded for the workspace) to hide the "Apply fix" / "Generate fix"
actions rather than showing them and failing on click.

Alternative considered: silently clone-apply-discard just to preview the diff
inline. Rejected as scope creep for this change — the proposal explicitly
scoped fix out; revisit as a separate change if requested.

### 5. Cloud project creation flow

New endpoint, structurally parallel to `clone_project` in
`api/routes/projects.py`, but it does not clone at creation time — it only
needs to reach the remote once to detect the default branch and languages for
the project card, then discards that peek. Reusing `clone_repository` for a
one-shot ephemeral clone (into a temp dir, `inspect_project`, then delete) is
the simplest correct option and reuses `detect_base_branch`/`detect_languages`
without new Git plumbing. The web app adds a third creation entry point
("Review a remote repository — cloud only") on the Projects screen showing the
URL + branch fields; the resulting card renders a globe/cloud icon
(`components/ui`) next to the project name (new small icon usage, not a new
design-system component).

### 6. UI badge

A `ProjectKind`-keyed badge/icon next to the name in `project-workspace.tsx`
and wherever project cards render on the dashboard — cloud icon for `CLOUD`,
nothing (or a small "cloned" hint, unchanged) for `LOCAL_OPEN`/`LOCAL_CLONE`.
Purely presentational; no new data beyond `kind` already being on the project
response.

## Risks / Trade-offs

- **[Risk] Review of a large remote repo without `--depth` clones the full
  history, which is slower than local-open/clone flows the user already
  controls.** → Mitigation: same cost model as today's `clone_project` (also
  full clone); document the expectation, revisit shallow-clone-with-fallback
  only if real usage shows it matters.
- **[Risk] Network/auth failures (private repo without a usable credential)
  surface mid-review instead of at project creation, since the real clone
  happens per-run.** → Mitigation: the creation-time peek clone (Decision 5)
  already validates reachability and auth before the project is saved, so a
  later per-run clone failing would indicate a transient or revoked-credential
  problem, not a first-time surprise; surface it as a normal review-failed
  state (`ReviewStatus.FAILED`), consistent with how other git errors already
  surface today.
- **[Risk] A crash between clone and cleanup (process killed, not just task
  cancelled) leaves an orphaned temp directory.** → Mitigation: OS temp
  directories are already expected to be reaped by the OS/user eventually;
  this is no worse than any other tool using `tempfile`. Optionally, `doctor`
  command could report leftover `revai-cloud-*` dirs as a housekeeping check
  in a follow-up change — not required for this one.
- **[Trade-off] No API-based (GitHub/GitLab REST) fetching means private repos
  need SSH keys or HTTPS PATs configured in the user's normal `git` credential
  flow (credential helper, SSH agent) — RevAI does not manage this
  credential.** Accepted per the explore-mode decision: maximizing code reuse
  and provider-agnosticism was preferred over building provider-specific API
  clients.

## Migration Plan

1. Bump `SCHEMA_VERSION`; add `_migrate_vN_to_vN+1` in `storage/migrations.py`
   backfilling `kind` on existing `Project` documents (`LOCAL_CLONE` if
   `remote_url` is set, else `LOCAL_OPEN`); `path` stays populated for all
   pre-existing documents so no data is lost.
2. Add `ProjectKind` enum, widen `Project.path` to `str | None`, add
   `ephemeral_clone()` in `git/repo.py`.
3. Wire the deterministic/AI pipeline branch (Decision 2) behind
   `project.kind is ProjectKind.CLOUD`; add tests mirroring the existing
   `test_projects.py`/`test_review_routes.py` fixtures for a cloud project.
4. Add the creation endpoint + route tests; reject fix requests (Decision 4)
   with a test asserting the specific error key.
5. Web: creation entry point, cloud badge, hide fix actions for cloud
   projects; component tests mirroring `branch-select.test.tsx` patterns.
6. No rollback concerns beyond a normal revert — no data migration is
   destructive (old documents just gain a field with a safe default).

## Open Questions

- Should the creation-time "peek clone" (Decision 5) also run a lightweight
  reachability/auth check that's distinguishable from "repo doesn't exist" vs
  "no credentials," or is today's generic `GitError` surface (as used by
  `clone_project`) good enough to start with?
- Is a single "target branch reviewed against base branch" review scope
  sufficient for v1 of cloud projects, or should whole-project/selected-files
  scopes (`ReviewScope`) also be supported from day one? (Assumed: yes to
  branch-diff only initially, matching the example in the exploration; other
  scopes need the same ephemeral clone and are low-cost to add later but are
  left out of `tasks.md` unless confirmed.)
