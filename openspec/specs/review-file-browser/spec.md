# review-file-browser Specification

## Purpose
TBD - created by archiving change improve-review-setup-navigation. Update Purpose after archive.
## Requirements
### Requirement: File universe controls
The Review setup file browser SHALL let the user display either all files tracked at Head or all files changed by the Branch diff between Base and Head. These controls SHALL affect presentation only and SHALL display the total for each universe.

#### Scenario: Branch diff changed universe
- **WHEN** the user views the `Changed` universe for different Base and Head refs
- **THEN** the browser lists the same changed paths reported by the Branch diff preview, including paths removed from Head

#### Scenario: Same-ref working tree changes
- **WHEN** Base and Head are the same ref and the user views the `Changed` universe
- **THEN** the browser lists the tracked and untracked working-tree changes included by the existing Branch diff semantics

#### Scenario: All tracked files
- **WHEN** the user selects the `All` universe
- **THEN** the browser lists every path tracked at Head and does not add ignored or untracked paths merely because they exist in the working directory

### Requirement: Contextual file universe defaults
The file browser SHALL select its initial universe from the active review scope and SHALL reapply that contextual default whenever the review scope changes.

#### Scenario: Branch diff default
- **WHEN** Review setup opens with Branch diff scope or the user changes the scope to Branch diff
- **THEN** the file browser selects the `Changed` universe

#### Scenario: Snapshot scope defaults
- **WHEN** the user changes the scope to Selected files or Whole project
- **THEN** the file browser selects the `All` universe

#### Scenario: Manual override within a scope
- **WHEN** the user manually changes the universe without changing review scope
- **THEN** the selected universe remains active until the scope changes again

### Requirement: Presentation controls do not change review semantics
Changing file universe, search query, layout, or folder expansion SHALL NOT modify review scope, selected-file state, or the files sent in a review request.

#### Scenario: Hidden selected files remain selected
- **WHEN** a selected file becomes hidden by search, universe selection, or folder collapse
- **THEN** it remains selected and the selected count continues to include it

#### Scenario: Navigation changes preserve request payload
- **WHEN** the user changes only presentation controls and then starts a review
- **THEN** the review request uses the same scope and selected paths it would have used before those presentation changes

### Requirement: File search
The file browser SHALL provide a case-insensitive substring search that matches both file basenames and complete repository-relative paths. It SHALL identify how many files are visible out of the active universe and provide a specific empty state when no path matches.

#### Scenario: Search by basename
- **WHEN** the user enters part of a filename with different letter casing
- **THEN** every active-universe file whose basename contains that text is visible

#### Scenario: Search by path
- **WHEN** the user enters a directory fragment or full relative-path fragment
- **THEN** every active-universe file whose repository-relative path contains that text is visible

#### Scenario: No search matches
- **WHEN** no file in the active universe matches the normalized query
- **THEN** the browser shows a no-matching-files state rather than the no-files-in-universe state

#### Scenario: Context change clears stale search
- **WHEN** the user changes Scope, Base, or Head
- **THEN** the file search is cleared before the new context is presented

### Requirement: Flat and tree layouts
The file browser SHALL provide flat-list and folder-tree layouts over the identical searched file set. Flat list SHALL be the initial layout, and changing review scope SHALL preserve the current layout.

#### Scenario: Flat list rendering
- **WHEN** the flat layout is selected
- **THEN** every visible file is rendered once with its complete repository-relative path in response order

#### Scenario: Tree rendering
- **WHEN** the tree layout is selected
- **THEN** visible files are grouped by their `/`-separated folders and each file appears exactly once

#### Scenario: Folder expansion
- **WHEN** the user collapses or expands an individual folder or invokes expand-all or collapse-all
- **THEN** the corresponding descendant rows change visibility without changing the underlying file set or selections

#### Scenario: Search reveals ancestors
- **WHEN** a search matches a file inside a folder that the user previously collapsed
- **THEN** the matching file and all directory ancestors needed to locate it are temporarily visible without permanently changing the saved collapsed state

### Requirement: Non-selectable changed paths
In Selected files scope, a changed path that is not tracked at Head SHALL remain visible in the `Changed` universe but SHALL NOT be addable to the selected-files snapshot.

#### Scenario: Deleted or untracked path in Selected files
- **WHEN** the `Changed` universe contains a path absent from the Head tracked tree while Selected files scope is active
- **THEN** its selection control is disabled and an accessible explanation states that it is available through Branch diff but not the selected-files snapshot

### Requirement: Accessible and localized file navigation
File-browser controls, counts, empty states, folder actions, and non-selectable explanations SHALL be operable and understandable with keyboard and pointer input in both `en-US` and `pt-BR`.

#### Scenario: Keyboard file navigation
- **WHEN** a keyboard user focuses universe, search, layout, or folder controls
- **THEN** each control has a visible focus state, an accessible name, and performs the same action available to pointer users

#### Scenario: Brazilian Portuguese locale
- **WHEN** the configured UI locale is `pt-BR`
- **THEN** all newly introduced file-browser text and accessibility labels are presented in Brazilian Portuguese

