# ephemeral-review-execution Specification

## Purpose
TBD - created by archiving change cloud-only-review-projects. Update Purpose after archive.
## Requirements
### Requirement: Review execution uses an ephemeral clone for cloud projects
When a review runs for a project of kind `cloud`, the system SHALL clone the
project's remote repository into a temporary directory for the duration of
that single review run, run the existing review pipeline (diff collection,
deterministic analyzers, AI stage) against that temporary directory exactly as
it would against a persistent local project, and delete the temporary
directory unconditionally when the run ends.

#### Scenario: Successful cloud review leaves no repository content behind
- **WHEN** a review completes successfully for a cloud project
- **THEN** the system persists the resulting `Review` (findings, stats,
  metadata) to local storage, and no cloned repository files remain on disk
  after the run finishes

#### Scenario: Failed cloud review still cleans up
- **WHEN** a review for a cloud project fails partway through (git error,
  analyzer crash, AI provider error, or an unhandled exception)
- **THEN** the temporary clone directory is deleted before the review run's
  execution context exits, regardless of the failure point

#### Scenario: Cancelled cloud review still cleans up
- **WHEN** a running review for a cloud project is cancelled by the user
- **THEN** the temporary clone directory is deleted as part of the
  cancellation, leaving no repository content on disk

#### Scenario: Cloud review diffs the selected branch against the base branch
- **WHEN** a user starts a review for a cloud project, selecting a branch to
  review
- **THEN** the system reviews the commits on that branch that are not on the
  project's configured base branch, using the same branch-diff scope
  semantics as local projects

### Requirement: Fix and apply-patch are unavailable for cloud projects
The system SHALL NOT allow a suggested patch to be applied to a finding that
belongs to a review of a cloud project, because no persistent working tree
exists to apply the patch into.

#### Scenario: API rejects a fix request for a cloud project's finding
- **WHEN** a fix-apply request is made for a finding that belongs to a review
  of a cloud project
- **THEN** the system rejects the request with a distinct error indicating
  fix/apply is unavailable for cloud projects, without attempting any patch
  or git operation

#### Scenario: UI hides fix actions for cloud project findings
- **WHEN** a finding card is rendered for a review that belongs to a cloud
  project
- **THEN** the "Apply fix" and "Generate fix" actions are not shown for that
  finding

