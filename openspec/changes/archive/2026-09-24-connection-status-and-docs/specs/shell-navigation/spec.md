## ADDED Requirements

### Requirement: Every destination appears once in the primary navigation
The primary navigation SHALL NOT offer the same destination both as a top-level entry
and as an entry inside the settings menu. Settings sub-pages SHALL be reachable
through the settings menu, and the top level SHALL be reserved for the main
destinations: projects, insights, documentation and settings.

#### Scenario: Settings sub-pages are not duplicated at the top level
- **WHEN** the user inspects the primary navigation
- **THEN** the appearance and data settings appear only inside the settings menu, and
  the top level lists projects, insights, documentation and settings

#### Scenario: Settings sub-pages remain reachable
- **WHEN** the user opens the settings menu
- **THEN** it lists the engine, connection, skills and prompts, appearance and data
  pages, and each navigates to its page

#### Scenario: Narrow viewport menu mirrors the same structure
- **WHEN** the navigation is viewed on a narrow screen
- **THEN** the collapsed menu offers the same destinations as the wide layout, with no
  destination present in one and missing from the other

### Requirement: Settings menu is defined once
The list of settings sub-pages SHALL be defined in a single place and used by both the
settings menu and the settings breadcrumb, so a newly added settings page cannot
appear in one and be missing from the other.

#### Scenario: Adding a settings page updates both surfaces
- **WHEN** a settings page is added to the shared list
- **THEN** it appears in the settings menu and in the settings breadcrumb menu without
  a second list being edited

### Requirement: Connection status is not surfaced on the projects screen
The projects screen SHALL NOT display an API connection indicator. Connection status
SHALL be surfaced only by the global warning banner and the connection settings
screen.

#### Scenario: No status chip on the projects screen
- **WHEN** the user opens the projects screen while the backend is reachable
- **THEN** no API connection indicator is rendered in its header

#### Scenario: Unreachable backend still reports the failure
- **WHEN** the user opens the projects screen while the backend is unreachable
- **THEN** the screen still reports that projects could not be loaded, and the global
  banner conveys the connection problem
