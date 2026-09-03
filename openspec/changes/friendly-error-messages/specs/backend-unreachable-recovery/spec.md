## ADDED Requirements

### Requirement: Dedicated backend-unreachable screen on settings pages
When a settings page (`/settings/appearance`, `/settings/engine`) cannot load
its initial configuration because the backend API is unreachable, the page
SHALL render a dedicated recovery screen instead of a minimal placeholder
message. The screen SHALL state clearly that the backend is unreachable, name
the expected API address, and explain that this commonly means the Docker
container is not running or not yet healthy.

#### Scenario: Appearance settings page cannot reach the backend
- **WHEN** the appearance settings page's initial configuration fetch fails
  because the API is unreachable
- **THEN** the page renders the dedicated recovery screen naming the expected
  API address and describing the likely Docker-related cause, instead of the
  form or a bare one-line message

#### Scenario: Engine settings page cannot reach the backend
- **WHEN** the engine settings page's initial configuration fetch fails
  because the API is unreachable
- **THEN** the same dedicated recovery screen is rendered

### Requirement: Actionable diagnostic guidance on the recovery screen
The recovery screen SHALL display the underlying technical error detail in a
visually secondary, monospaced element, and SHALL show suggested diagnostic
commands (`docker compose ps` and `docker compose logs api`) in a
monospaced block.

#### Scenario: Technical detail is visible but de-emphasized
- **WHEN** the recovery screen is shown
- **THEN** the raw error detail is visible on screen in a monospaced,
  visually secondary element, and the suggested `docker compose` commands are
  shown in a separate monospaced block

### Requirement: Copyable AI troubleshooting prompt
The recovery screen SHALL provide a button labeled to copy an AI
troubleshooting prompt to the clipboard. The prompt text itself SHALL NOT be
displayed anywhere on screen at any time. The copied prompt SHALL be a
structured, self-contained description of the problem — naming the Docker
Compose service (`api`), the expected port, the health endpoint, and concrete
remediation steps — with the actual captured error detail interpolated into
it, suitable for pasting directly into a coding agent.

#### Scenario: Copying the prompt does not reveal it on screen
- **WHEN** the user views the recovery screen without clicking the copy button
- **THEN** no prompt text is rendered anywhere in the page's visible content
  or accessible DOM text

#### Scenario: Copy button places the structured prompt on the clipboard
- **WHEN** the user clicks the "copy AI troubleshooting prompt" button
- **THEN** the clipboard contains a prompt that names the `api` Docker Compose
  service, the expected port and health endpoint, concrete remediation steps,
  and the specific technical error detail captured from the failed request

#### Scenario: Copy action gives feedback without leaking the prompt
- **WHEN** the copy action succeeds
- **THEN** the button shows a transient confirmation state (e.g. a
  "Copied" label) without displaying the copied text itself

### Requirement: Retry action
The recovery screen SHALL provide a way to retry loading the settings page's
configuration without a full manual page reload.

#### Scenario: Retry succeeds once the backend recovers
- **WHEN** the backend becomes reachable and the user activates the retry
  action on the recovery screen
- **THEN** the page re-fetches its configuration and, on success, renders the
  normal settings form instead of the recovery screen
