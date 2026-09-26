## ADDED Requirements

### Requirement: Aggregated status endpoint
The backend SHALL expose `GET /api/status` returning, in a single response, the
backend's own health information, an AI section describing the configured
provider's usability together with the readiness of every known provider, and a
local SonarQube section. The endpoint SHALL return HTTP 200 even when a probed
component is unhealthy, because a failed probe is data to render rather than a
request error.

#### Scenario: Every section is reported in one response
- **WHEN** a client requests `GET /api/status` while the backend is running
- **THEN** the response has HTTP status 200 and contains an `api` section with the
  application version and environment, an `ai` section with the configured
  provider id, its state, its usability, the ids of all ready providers, the ids of
  all providers whose state could not be determined, the total provider count and a
  verdict, and a `sonarqube` section with its enabled flag and server state

#### Scenario: An unhealthy provider does not fail the request
- **WHEN** the configured AI provider is not authenticated and a local SonarQube
  server is not running
- **THEN** `GET /api/status` still returns HTTP 200, reporting the unhealthy states
  in the response body rather than an error status

#### Scenario: Broken configuration file is reported as a client error
- **WHEN** the configuration or credentials file cannot be parsed
- **THEN** `GET /api/status` fails with HTTP 422 carrying the structured error
  contract naming the file and field, consistent with the existing provider
  endpoints

### Requirement: Status results are cached with an explicit refresh
The status service SHALL serve results from a short-lived in-process cache instead of
probing on every request, because determining AI provider readiness spawns CLI
subprocesses. The response SHALL state when the data was collected and whether it
came from the cache. A request with `refresh=true` SHALL bypass the cache and
collect fresh data.

#### Scenario: Repeated requests within the TTL do not re-probe
- **WHEN** two `GET /api/status` requests are made within the cache TTL
- **THEN** the second response is served from the cache, is marked as cached,
  reports the same collection timestamp as the first, and performs no additional
  provider probing

#### Scenario: Explicit refresh re-probes
- **WHEN** a client requests `GET /api/status?refresh=true` while a cached result is
  still fresh
- **THEN** the providers are probed again, the response is marked as not cached, and
  it carries a newer collection timestamp

#### Scenario: Stale cache is replaced automatically
- **WHEN** a `GET /api/status` request arrives after the cached result has exceeded
  its TTL
- **THEN** the data is collected again and the fresh result replaces the cached one

### Requirement: AI verdict is determined by the configured provider
The `ai` section's verdict SHALL be derived from the provider selected in the engine
configuration, not from the existence of any usable provider, because a review runs
with the configured provider. The verdict SHALL distinguish: the configured provider
being usable, the configured provider being broken while another provider is ready,
no provider being ready at all, and the configured provider's state being
indeterminable.

#### Scenario: Configured provider is ready
- **WHEN** the configured provider probes as ready
- **THEN** the verdict reports that AI is usable, regardless of the state of the
  other providers

#### Scenario: Configured provider is broken while another is ready
- **WHEN** the configured provider requires authentication and a different provider
  probes as ready
- **THEN** the verdict reports that the configured provider is broken, and the
  response lists the ready provider ids so the interface can name an alternative

#### Scenario: No provider is ready
- **WHEN** no provider probes as ready and the configured provider is not usable
- **THEN** the verdict reports that no provider is ready

#### Scenario: Configured provider state cannot be determined
- **WHEN** the configured provider's state is indeterminable, as with a CLI that
  exposes no authentication-status command
- **THEN** the verdict reports the indeterminable state as its own value, distinct
  from both usable and broken

#### Scenario: A recognised but unimplemented provider never counts as ready
- **WHEN** a provider is recognised by RevAI but its adapter is not implemented
- **THEN** it is excluded from the ready provider ids

### Requirement: Backend returns classifications, not interface copy
The status response SHALL carry machine-readable states, identifiers and verdict
values only, and SHALL NOT contain user-facing sentences intended for direct
display. Remediation text already produced by provider probing may be passed
through unchanged.

#### Scenario: Response carries no untranslated interface sentences
- **WHEN** any `GET /api/status` response is inspected
- **THEN** its verdict and state fields are enumerated values that the interface maps
  to localized copy, rather than prose composed by the backend

### Requirement: Connection settings screen
The application SHALL provide a settings screen at `/settings/connection`, labeled
"API & AI" in English and "API e IA" in Brazilian Portuguese, that shows the live
backend status, the AI provider status including the readiness scoreboard across all
providers, and the local SonarQube status. The screen SHALL offer a way to re-check
the status on demand, a link to the engine settings screen for configuration, and a
link to the documentation page explaining how to start the backend.

#### Scenario: Healthy state is shown with detail
- **WHEN** the user opens `/settings/connection` while the backend is running and the
  configured provider is ready
- **THEN** the screen reports the backend as connected with its address and version,
  reports the configured provider as ready, shows how many providers of the total are
  ready, and shows when the status was collected

#### Scenario: Broken provider shows its remediation
- **WHEN** the configured provider is not usable and the backend reported a
  remediation command for it
- **THEN** the screen shows the provider's state and displays that remediation
  verbatim in a monospaced element

#### Scenario: Re-check collects fresh data
- **WHEN** the user activates the re-check action
- **THEN** the interface requests a refreshed status bypassing the cache, shows a busy
  state while collecting, and then renders the new result with an updated collection
  timestamp

#### Scenario: Navigation to configuration and documentation
- **WHEN** the user views `/settings/connection`
- **THEN** the screen offers a control that navigates to `/settings/engine` and a link
  to the documentation page describing how to start the backend

#### Scenario: Backend unreachable while viewing the screen
- **WHEN** the status request fails because the backend is unreachable
- **THEN** the screen renders the existing backend-unreachable recovery content,
  including the diagnostic commands and the retry action, instead of an empty or
  partially filled panel

#### Scenario: SonarQube shown as informational when disabled
- **WHEN** local SonarQube is disabled in the analyzer configuration
- **THEN** the screen reports it as disabled without presenting it as a problem

### Requirement: Global connection warning banner
The application SHALL render a warning banner directly below the primary navigation,
spanning the full window width, with a small height, an amber surface, an alert icon,
a single short message, one action navigating to `/settings/connection`, and a dismiss
control. At most one banner SHALL be visible at any time.

#### Scenario: Backend unreachable produces a single banner
- **WHEN** the backend cannot be reached, which also makes the provider state
  indeterminable
- **THEN** exactly one banner is shown, reporting the backend as unreachable, and no
  separate provider banner appears

#### Scenario: Broken configured provider names a ready alternative
- **WHEN** the backend is reachable, the configured provider is not usable, and
  another provider is ready
- **THEN** the banner states that the configured provider needs attention and names a
  ready provider, with the action linking to `/settings/connection`

#### Scenario: No provider ready
- **WHEN** the backend is reachable and no provider is ready
- **THEN** the banner states that no AI provider is ready

#### Scenario: Indeterminable provider state warns without claiming failure
- **WHEN** the configured provider's state cannot be determined
- **THEN** the banner states that the connection could not be confirmed, rather than
  reporting a failure

#### Scenario: Disabled SonarQube never triggers the banner
- **WHEN** local SonarQube is not running and is disabled in the analyzer
  configuration
- **THEN** no banner is shown for SonarQube

#### Scenario: Enabled but unavailable SonarQube triggers the banner
- **WHEN** local SonarQube is enabled in the analyzer configuration and its server is
  not running, while the backend and the configured provider are healthy
- **THEN** a banner reports SonarQube as unavailable

### Requirement: Banner renders nothing before the first status answer
The banner SHALL render no element — no placeholder and no skeleton — until the first
status response has been received, so the page does not shift layout after load.

#### Scenario: Nothing is rendered while probing
- **WHEN** the application has loaded but the first status response has not arrived
- **THEN** no banner element exists in the document

#### Scenario: Nothing is rendered in the healthy state
- **WHEN** the first status response reports everything healthy
- **THEN** no banner element exists in the document

### Requirement: Banner alerts only after a transient-failure debounce
The banner SHALL appear only after a problem has been confirmed rather than on its
first observation, so that restarting the backend does not flash a warning.

#### Scenario: A single transient failure does not show the banner
- **WHEN** one status attempt fails and the next attempt succeeds within the
  debounce window
- **THEN** no banner is ever displayed

#### Scenario: A persistent failure shows the banner
- **WHEN** a problem is still present after the debounce window
- **THEN** the banner appears

### Requirement: Banner dismissal is per problem kind and per session
Dismissing the banner SHALL hide only the kind of problem that was dismissed, for the
current browser session. A different problem kind appearing later SHALL show the
banner again, and a new session SHALL start with no dismissals.

#### Scenario: Dismissal hides the current problem
- **WHEN** the user activates the dismiss control
- **THEN** the banner disappears and does not reappear for that same problem kind
  during the session, including across navigations

#### Scenario: A different problem still warns
- **WHEN** the user has dismissed the backend-unreachable banner and, later in the
  same session, the backend recovers but the configured provider becomes unusable
- **THEN** the banner appears again for the provider problem

#### Scenario: Dismissals do not survive a new session
- **WHEN** the user dismisses a banner and later opens the application in a new
  browser session while the same problem persists
- **THEN** the banner is shown again

### Requirement: Banner is suppressed on the connection screen
The banner SHALL NOT be rendered while the user is viewing `/settings/connection`,
because that screen already presents the full diagnosis.

#### Scenario: No banner on the connection screen
- **WHEN** a problem exists and the user navigates to `/settings/connection`
- **THEN** no banner is rendered on that screen, and it reappears on other screens
  while the problem persists and remains undismissed

### Requirement: Status is revalidated after actions that can change it
The interface SHALL re-read the status after user actions that can change it —
saving engine configuration, storing or deleting a credential, verifying a provider,
and starting or stopping local SonarQube — rather than waiting for a cache expiry.

#### Scenario: Saving engine settings refreshes the status
- **WHEN** the user saves a change to the engine configuration
- **THEN** the interface re-reads the status and the banner reflects the new
  configuration without a manual page reload

#### Scenario: Storing a credential clears a stale warning
- **WHEN** the configured provider was warning for missing authentication and the
  user stores a valid credential for it
- **THEN** the status is re-read and the banner disappears without a manual page
  reload
