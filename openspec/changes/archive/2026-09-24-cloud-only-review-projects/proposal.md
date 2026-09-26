## Why

RevAI currently supports two project kinds, and both materialize the repository
permanently on disk under a folder the user chooses: open an existing local Git
folder, or `git clone` a remote into a persistent destination. Users who want to
review a remote repository without keeping a permanent local checkout (e.g.
reviewing someone else's branch once, or working from a machine where disk
persistence of the source is undesirable) have no option that matches RevAI's
"local-first" posture applied in reverse — never keep the repository, only keep
the review. This adds that third project kind.

## What Changes

- New project kind, **Cloud project**: created from a remote Git URL and a target
  branch (reviewed against the project's base branch), with no persistent local
  checkout. `git clone` still happens, but into an ephemeral temp directory that
  is deleted unconditionally (success, failure, or cancellation) once the review
  run finishes.
- The existing deterministic pipeline (`materialized_tree`, chunking, analyzers)
  and AI pipeline run unmodified against the ephemeral clone — no new review
  logic, only a new source for the working directory.
- Only the `Review` record (findings, stats, metadata) is persisted to
  `~/.revai/reviews/`, exactly like today. No repository content, patches, or
  clone artifacts survive past the run.
- **Fix / apply-patch is out of scope for cloud projects.** `revai fix` and the
  finding card's "Apply fix" action require a persistent working tree to apply
  a patch into and are unavailable for this project kind; the UI hides/disables
  that action and the API rejects fix requests for cloud projects with a clear
  error.
- Project dashboard/workspace UI shows a cloud/globe badge on cloud projects to
  visually distinguish them from local-open and local-clone projects.
- **BREAKING**: none — this is purely additive; existing local and cloned
  projects are unaffected.

## Capabilities

### New Capabilities
- `cloud-projects`: creation, storage, and lifecycle of projects backed by an
  ephemeral remote clone instead of a persistent local path — covers the new
  project kind, its data model, and the API/UI surface for creating one.
- `ephemeral-review-execution`: running the existing review pipeline (branch
  diff, deterministic analyzers, AI stage) against a temporary clone that is
  guaranteed to be deleted after the run, regardless of outcome.

### Modified Capabilities
- (none yet — no existing spec files are archived under `openspec/specs/` to
  amend; the review-execution and fix-application behavior touched here has
  not been captured as a synced spec previously)

## Impact

- **Backend (`platform/api/revai`)**:
  - `domain/models.py` — `Project` needs to represent "no persistent path" (kind
    discriminator, nullable path) while keeping `remote_url` and `base_branch`.
  - `git/repo.py` — new ephemeral-clone helper alongside `clone_repository`,
    reusing `diff_preview`/`materialized_tree` unchanged.
  - `api/routes/projects.py` — new creation endpoint/flow for cloud projects
    (distinct from `open_project`/`clone_project`).
  - `api/routes/reviews.py`, `pipeline/runner.py` — review run must clone to a
    temp dir first for cloud projects, then always clean up.
  - `fixes/service.py`, `api/routes/fixes.py` — must reject fix requests for
    projects without a persistent path.
- **Frontend (`platform/web`)**: project creation flow gets a third entry point;
  project cards/workspace show a cloud badge; finding cards hide "Apply fix"
  for cloud projects.
- **Docs/README**: new section describing the cloud project kind and its
  scope limitation (no fix/apply).
