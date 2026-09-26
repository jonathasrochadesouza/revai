## 1. Domain model and storage

- [x] 1.1 Add `ProjectKind` (`LOCAL_OPEN`, `LOCAL_CLONE`, `CLOUD`) to `domain/enums.py`; bump `SCHEMA_VERSION`
- [x] 1.2 Widen `Project.path` to `str | None` and add `kind: ProjectKind` on `Project` in `domain/models.py`
- [x] 1.3 Add a migration in `storage/migrations.py` backfilling `kind` on existing documents (`LOCAL_CLONE` if `remote_url` set, else `LOCAL_OPEN`) and add a migration test alongside `test_migrations.py`
- [x] 1.4 Add a helper (e.g. `Project.require_path()`) that raises a distinct, named error when `path` is `None`, replacing bare `Path(project.path)` call sites

## 2. Ephemeral clone plumbing

- [x] 2.1 Add `ephemeral_clone(remote: str) -> Iterator[Path]` context manager in `git/repo.py`, sibling to `materialized_tree`, using `tempfile.TemporaryDirectory` + full `git clone` (no `--depth`)
- [x] 2.2 Add unit tests for `ephemeral_clone`: successful clone yields a working directory, directory is removed after the `with` block exits normally, and removed when the block raises

## 3. Review pipeline integration

- [x] 3.1 In `pipeline/runner.py::run_deterministic_pipeline`, branch on `project.kind is ProjectKind.CLOUD` to wrap execution in `ephemeral_clone(project.remote_url)` instead of `Path(project.path)`
- [x] 3.2 Apply the same branching to the AI review route path in `api/routes/reviews.py` (`create_ai_review` / `create_deterministic_review`) wherever it resolves the project's working directory
- [x] 3.3 Verify cancellation (`cancel_review`) still tears down the ephemeral clone by keeping the clone's `with` block inside the same task that gets cancelled
- [x] 3.4 Add integration tests mirroring `test_review_routes.py` fixtures for a cloud project: successful review persists only the `Review` record and leaves no clone directory behind; a failed review (git error, analyzer crash) still cleans up; a cancelled review still cleans up

## 4. Cloud project creation

- [x] 4.1 Add a creation endpoint in `api/routes/projects.py` (e.g. `create_cloud_project`) that takes a remote URL and optional base branch override, does a one-shot ephemeral clone to detect base branch/languages via `inspect_project`/`detect_base_branch`/`detect_languages`, then discards the clone and saves a `Project` with `kind = CLOUD`, `path = None`
- [x] 4.2 Reject creation with a specific error when the remote is unreachable, unauthenticated, or not a Git repository
- [x] 4.3 Add route tests mirroring `test_projects.py`: successful cloud creation, unreachable-URL rejection, and confirming no directory survives creation

## 5. Fix/apply rejection for cloud projects

- [x] 5.1 In `fixes/service.py::apply_finding_fix`, add an early check that raises a distinct error (`fix.unavailable_for_cloud_project`) when the finding's project `kind is ProjectKind.CLOUD`
- [x] 5.2 Ensure `api/routes/fixes.py` maps that error to a clear, user-actionable API response (not a generic 404/500)
- [x] 5.3 Add tests in `test_fix_service.py` / `test_fix_routes.py` asserting the specific error for a cloud project's finding, and confirming no git/patch operation is attempted

## 6. Web app: creation flow and badge

- [x] 6.1 Add a third project-creation entry point on the Projects screen ("Review a remote repository — cloud only") with URL + base branch fields, calling the new creation endpoint
- [x] 6.2 Render a cloud/globe badge next to the project name in `project-workspace.tsx` and any dashboard project card when `kind === "cloud"`
- [x] 6.3 Hide "Apply fix" and "Generate fix" actions in `finding-card.tsx` when the finding's project is a cloud project
- [x] 6.4 Add/extend component tests for the new creation form, the badge rendering, and the hidden fix actions

## 7. Docs

- [x] 7.1 Add a README/docs section describing the cloud project kind, how it's created, and the fix/apply limitation
