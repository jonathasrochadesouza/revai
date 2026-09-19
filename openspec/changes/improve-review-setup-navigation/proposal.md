## Why

The Review setup file panel always renders every file tracked at the selected Head, even when Branch diff will review only the files changed between Base and Head. Large repositories are therefore difficult to navigate, and the native branch selects and unexplained quality-command fields add avoidable friction when configuring a review.

## What Changes

- Add presentation-only `Changed` and `All` file-universe controls to the Review setup file panel, with contextual defaults per review scope and counts that make hidden results explicit.
- Add case-insensitive file search by basename or full repository-relative path.
- Add flat-list and collapsible-folder-tree layouts over the same file set, including accessible folder expansion controls and search-aware ancestor visibility.
- Replace the Base, Head, and Default base branch native selects with one reusable, searchable, keyboard-accessible branch selector.
- Add concise, accessible help tooltips for the Checkstyle, Tests, and Build project quality commands.
- Add English and Brazilian Portuguese labels, empty states, descriptions, and accessibility text for the new controls.

## Capabilities

### New Capabilities

- `review-file-browser`: Presentation-only file-universe filtering, file search, counts, and interchangeable flat/tree navigation in Review setup.
- `searchable-branch-selector`: Searchable and keyboard-accessible selection for every branch field in Review setup.
- `quality-command-guidance`: Accessible contextual explanations for Checkstyle, Tests, and Build command configuration.

### Modified Capabilities

None. The repository has no canonical specs under `openspec/specs/` yet.

## Impact

- Frontend: Review setup orchestration and project-quality form in `platform/web/src/components/projects/project-workspace.tsx`, with focused UI components extracted as appropriate.
- Localization: new interface strings in `platform/web/src/components/ui-preference-bootstrap.tsx` for `en-US` and `pt-BR` behavior.
- Data flow: the existing project tree remains the source for all tracked files, while an independently loaded Branch diff preview supplies changed-file paths regardless of the active review scope.
- API: no endpoint or response-contract change is required; existing tree, diff, and project branch data are sufficient.
- Dependencies: no new runtime dependency is expected.
- Coordination: the active `friendly-error-messages` change is independent but may touch the same Review setup and localization files during implementation.
