# searchable-branch-selector Specification

## Purpose
TBD - created by archiving change improve-review-setup-navigation. Update Purpose after archive.
## Requirements
### Requirement: Shared searchable branch selection
Review setup SHALL use the same searchable branch selector for Base, Head, and Default base branch. The selector SHALL filter the complete already-loaded local and remote branch list with a case-insensitive substring match.

#### Scenario: Search all branch fields
- **WHEN** the user opens Base, Head, or Default base branch and types a query
- **THEN** that selector lists only branch names containing the query regardless of letter casing

#### Scenario: Local and remote matches
- **WHEN** local and remote branch names both match the query
- **THEN** both kinds remain available for selection in their existing branch-name form

#### Scenario: No branch matches
- **WHEN** the query matches no loaded branch
- **THEN** the selector shows a localized no-results state and does not alter the current value

### Requirement: Branch values remain valid
The searchable branch selector SHALL be controlled by its caller and SHALL only emit a branch present in its supplied options. Typed search text SHALL NOT become a branch value.

#### Scenario: Select a valid result
- **WHEN** the user activates a filtered branch result
- **THEN** the selector emits that exact branch name, closes, and displays it as the current value

#### Scenario: Dismiss an incomplete search
- **WHEN** the user dismisses the selector without activating a result
- **THEN** the previously selected branch remains unchanged

### Requirement: Accessible combobox interaction
The branch selector SHALL support pointer and keyboard operation with an accessible relationship between its trigger, search input, popup, active option, and current value.

#### Scenario: Keyboard selection
- **WHEN** the selector is open and the user operates Arrow keys and Enter
- **THEN** focus or active-option state moves through the filtered results and Enter selects the active branch

#### Scenario: Escape dismissal
- **WHEN** the selector is open and the user presses Escape
- **THEN** it closes without changing the value and restores focus to its trigger

#### Scenario: Pointer selection
- **WHEN** the user activates a branch result with a pointer or touch input
- **THEN** the branch is selected with the same result as keyboard activation

### Requirement: Localized branch search
Search prompts, empty states, and accessibility labels for every branch selector SHALL be available in `en-US` and `pt-BR`.

#### Scenario: Brazilian Portuguese branch selector
- **WHEN** the configured UI locale is `pt-BR`
- **THEN** the branch search prompt, no-results state, and accessibility instructions are presented in Brazilian Portuguese

