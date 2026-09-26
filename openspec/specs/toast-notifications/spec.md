# toast-notifications Specification

## Purpose
TBD - created by archiving change friendly-error-messages. Update Purpose after archive.
## Requirements
### Requirement: Toast notification queue with FIFO capacity limit
The application SHALL provide a single, app-wide toast notification stack that
holds at most 3 visible notifications at a time. When a 4th notification is
pushed while 3 are already visible, the oldest visible notification SHALL be
removed immediately to make room for the new one (first-in, first-out
eviction), rather than the new notification being dropped or queued invisibly.

#### Scenario: Fourth toast evicts the oldest
- **WHEN** three toasts (A, B, C, pushed in that order) are currently visible
  and a fourth toast (D) is pushed
- **THEN** toast A is removed and the visible set becomes B, C, D

#### Scenario: Third toast does not evict anything
- **WHEN** two toasts are visible and a third is pushed
- **THEN** all three remain visible

### Requirement: Auto-dismiss with hover pause
Each toast SHALL automatically dismiss itself 10 seconds after it becomes
visible, unless the user's pointer is hovering over it. While the pointer
hovers over a toast, its dismiss countdown SHALL pause; when the pointer
leaves, the countdown SHALL resume from the time remaining at the moment it
was paused, not restart from 10 seconds.

#### Scenario: Toast dismisses after 10 seconds with no interaction
- **WHEN** a toast is pushed and the user never hovers it
- **THEN** it is automatically removed 10 seconds after it appeared

#### Scenario: Hovering pauses the dismiss countdown
- **WHEN** a toast has been visible for 6 seconds and the user hovers over it
  for 5 seconds before moving the pointer away
- **THEN** the toast is not dismissed while hovered, and is automatically
  removed 4 seconds after the pointer leaves (the remaining time from when
  the hover began)

### Requirement: Theme-inverted dark presentation
Toasts SHALL render with a color scheme that is independent of and visually
inverted relative to the current page theme, so they are always distinguishable
from both the page background and the `SaveBar` settings-save bar. When the
active page theme is light, the toast surface SHALL be a near-black background
with light, high-contrast text. When the active page theme is dark, the toast
surface SHALL be a light-gray background with dark, high-contrast text. This
color pairing SHALL NOT reuse the page's theme-remapped surface tokens (the
tokens that change value between light and dark page themes).

#### Scenario: Toast on a light-theme page
- **WHEN** the application's active theme is light and a toast is shown
- **THEN** the toast renders with a near-black background and light text,
  visually distinct from the surrounding light page and from the light
  `SaveBar`

#### Scenario: Toast on a dark-theme page
- **WHEN** the application's active theme is dark and a toast is shown
- **THEN** the toast renders with a light-gray background and dark text,
  visually distinct from the surrounding dark page surfaces

### Requirement: Non-settings-save error surfaces use toasts
Every error outside the settings-save flow SHALL be presented via the toast notification stack instead of a page-embedded ad hoc banner — including project list/workspace notices, review setup notices, the insights dashboard, the data export panel, the provider panel, and top-level failures of the open/clone-project dialog. The settings-save flow's existing `SaveBar` error presentation SHALL NOT be migrated to the toast and SHALL continue to render inline within the save bar.

#### Scenario: Insights dashboard load failure shows a toast
- **WHEN** the insights dashboard fails to load data from the API
- **THEN** a toast notification is shown reporting the failure, and no
  full-width inline error banner is rendered in place of the dashboard content

#### Scenario: Settings save failure still uses the save bar
- **WHEN** saving the appearance or engine settings form fails
- **THEN** the error is shown inside the existing `SaveBar` component at the
  bottom of the page, and no toast notification is pushed for that failure

#### Scenario: Clone-project top-level failure shows a toast
- **WHEN** cloning a repository from the "Clone from remote" dialog fails at
  the operation level (e.g. the remote could not be reached)
- **THEN** a toast notification reports the failure

### Requirement: Toast messages are localized
Toast notification text SHALL be produced using the same error translation
catalog used elsewhere in the application, rendering in the user's active
`ui.locale`.

#### Scenario: Toast renders in the active locale
- **WHEN** a backend error with a known `error_key` triggers a toast while the
  active locale is `pt-BR`
- **THEN** the toast displays the Portuguese-localized message, not the raw
  `error_key` or an English fallback

