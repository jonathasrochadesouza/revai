# quality-command-guidance Specification

## Purpose
TBD - created by archiving change improve-review-setup-navigation. Update Purpose after archive.
## Requirements
### Requirement: Quality command explanations
The Project quality commands form SHALL place a concise explanation beside each Checkstyle, Tests, and Build label that tells the user what the configured command is intended to validate.

#### Scenario: Checkstyle explanation
- **WHEN** the user opens help for Checkstyle
- **THEN** the interface explains that the command checks configured Java style and static-code rules

#### Scenario: Tests explanation
- **WHEN** the user opens help for Tests
- **THEN** the interface explains that the command runs the project's test suite to detect failures and regressions

#### Scenario: Build explanation
- **WHEN** the user opens help for Build
- **THEN** the interface explains that the command compiles or packages the project to validate dependencies, types, and generated artifacts

### Requirement: Accessible tooltip interaction
Each quality-command explanation SHALL use a focusable information trigger and a tooltip associated through accessible attributes. The same content SHALL be available through hover, keyboard focus, and tap or click without relying solely on an HTML `title` attribute.

#### Scenario: Keyboard access
- **WHEN** a keyboard user focuses a quality-command information trigger
- **THEN** the associated explanation becomes available without moving focus away from the trigger

#### Scenario: Pointer and touch access
- **WHEN** a user hovers over or activates the information trigger with pointer or touch input
- **THEN** the associated explanation becomes visible and does not change the command input value

#### Scenario: Tooltip dismissal
- **WHEN** an open tooltip loses its applicable focus or hover state, is dismissed by pointer interaction, or receives Escape
- **THEN** it closes without changing focus unexpectedly or modifying form data

### Requirement: Localized quality-command guidance
Quality-command tooltip content and accessibility labels SHALL be provided in `en-US` and `pt-BR` through the existing UI locale mechanism.

#### Scenario: Brazilian Portuguese guidance
- **WHEN** the configured UI locale is `pt-BR`
- **THEN** the Checkstyle, Tests, and Build explanations and their accessible trigger labels are presented in Brazilian Portuguese

