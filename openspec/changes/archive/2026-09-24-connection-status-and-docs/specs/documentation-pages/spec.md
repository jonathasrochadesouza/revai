## ADDED Requirements

### Requirement: In-app documentation section
The application SHALL provide a documentation section at `/docs` with its own
top-level entry in the primary navigation. The section SHALL contain multiple pages,
each addressable by its own URL, covering at minimum: getting started, starting the
backend, configuring providers, running a first review, findings and fixes, local
SonarQube, the CLI and CI usage, the `AGENTS.md` review agent, and privacy and data
handling.

#### Scenario: Documentation is reachable from the navigation
- **WHEN** the user activates the documentation entry in the primary navigation
- **THEN** the documentation section opens

#### Scenario: Each page has its own address
- **WHEN** the user opens a documentation page and copies the URL
- **THEN** that URL loads the same page directly, without passing through an index

#### Scenario: Unknown page address
- **WHEN** a documentation URL names a page that does not exist
- **THEN** the application renders its not-found response rather than an empty
  documentation frame

### Requirement: Sidebar navigation driven by a single page registry
The documentation section SHALL present a navigation sidebar on the left listing its
pages in groups, marking the current page. The sidebar, the set of valid page
addresses and the documentation breadcrumb SHALL be derived from one registry, so
they cannot list different pages.

#### Scenario: Current page is marked in the sidebar
- **WHEN** the user is viewing a documentation page
- **THEN** the sidebar shows that page as the current entry

#### Scenario: Sidebar and addresses cannot diverge
- **WHEN** a page is added to or removed from the registry
- **THEN** the sidebar listing, the valid addresses and the breadcrumb all change
  together, with no separate list to update

#### Scenario: Narrow viewport collapses the sidebar
- **WHEN** the documentation section is viewed on a narrow screen
- **THEN** the sidebar collapses into an expandable control instead of consuming the
  reading width

### Requirement: Documentation works with the backend stopped and without internet
Documentation pages SHALL NOT perform any request to the backend API or to any
external network resource in order to render, because the page explaining how to
start the backend is needed precisely when the backend is not running, and the
product must work with no internet connection.

#### Scenario: Backend stopped
- **WHEN** the backend API is not running and the user opens the page explaining how
  to start the backend
- **THEN** the page renders completely, including its commands, with no error state

#### Scenario: No internet connection
- **WHEN** the machine has no internet access and the user browses the documentation
- **THEN** every page renders completely, with any external references presented as
  supplementary rather than required to understand the page

### Requirement: Documentation prose is localized through the message catalog
Documentation prose SHALL be translated through the application's message catalog so
that both supported locales render complete pages. Commands, code blocks and product
names SHALL NOT be stored as catalog entries.

#### Scenario: Pages render in the selected locale
- **WHEN** the interface locale is Brazilian Portuguese
- **THEN** documentation titles, sidebar labels and prose render in Brazilian
  Portuguese

#### Scenario: Locale parity is enforced
- **WHEN** a documentation prose entry exists in one locale catalog but not the other
- **THEN** the existing catalog parity test fails

#### Scenario: Commands are identical in both locales
- **WHEN** a documentation page shows a shell command or a code block
- **THEN** that text is rendered from the page component rather than from the
  catalog, so the catalog parity test's prohibition on identical entries is not
  triggered

### Requirement: Backend startup page is a linkable recovery target
The documentation page describing how to start the backend SHALL document the local startup command (`cd platform/api` and `uv run revai-api`) as the primary path, SHALL live in the standalone Docusaurus docs site, and SHALL be reachable by a stable address that the connection status screen links to.

#### Scenario: Startup path is documented
- **WHEN** the user opens the backend startup page
- **THEN** it shows the local commands to start, inspect and read the logs of
  the API process

#### Scenario: Connection screen links to it
- **WHEN** the user follows the documentation link from the connection status screen
- **THEN** the backend startup page opens

#### Scenario: Repository instructions agree with the page
- **WHEN** the project README and the backend startup page are compared
- **THEN** they describe the same local startup path
