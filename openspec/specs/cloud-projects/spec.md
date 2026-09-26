# cloud-projects Specification

## Purpose
TBD - created by archiving change cloud-only-review-projects. Update Purpose after archive.
## Requirements
### Requirement: Cloud project creation
The system SHALL allow a user to create a project of kind `cloud` by supplying
a remote Git URL and a base branch, without creating a persistent local
working tree for that project.

#### Scenario: Creating a cloud project from a reachable public URL
- **WHEN** the user submits a remote Git URL and the repository is reachable
- **THEN** the system creates a `Project` with `kind = cloud`, `path = null`,
  `remote_url` set to the supplied URL, and `base_branch` detected from the
  remote (or left to be set explicitly), without leaving any cloned
  repository content on disk after creation completes

#### Scenario: Creating a cloud project from an unreachable or invalid URL
- **WHEN** the user submits a remote Git URL that cannot be cloned (network
  failure, authentication failure, or the URL does not point to a Git
  repository)
- **THEN** the system rejects the creation with a specific, user-actionable
  error and does not create a `Project` record

### Requirement: Cloud project has no persistent local path
A `Project` of kind `cloud` SHALL NOT have a persistent local directory
associated with it at rest. Any reference to the project's working directory
outside of an active review run SHALL fail with a distinct, named error
rather than resolving to an invalid or empty path.

#### Scenario: Reading a cloud project's path outside a review run
- **WHEN** any code path attempts to resolve a cloud project's working
  directory while no review is currently executing for that project
- **THEN** the system raises a distinct error indicating the project has no
  persistent path, rather than operating on an empty or default path

### Requirement: Cloud project visual indicator
The system SHALL visually distinguish cloud projects from local-open and
local-clone projects wherever project cards or headers are rendered.

#### Scenario: Cloud project card shows a cloud indicator
- **WHEN** a project of kind `cloud` is displayed on the dashboard or its
  workspace page
- **THEN** the UI renders a cloud/globe badge or icon next to the project
  name that is not shown for local-open or local-clone projects

