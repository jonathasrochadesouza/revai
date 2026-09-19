## Context

`RepositoryInspector` currently loads two related but different datasets together: the tracked tree at Head and a preview whose contents depend on the active review scope. The sidebar always renders the tracked tree, so Branch diff shows every tracked file even though the preview and eventual review use only changed files. The same large client component owns the project-quality form and native branch selects, and the frontend has no reusable combobox or tooltip primitives.

The existing API already exposes everything needed: the tree endpoint returns all files tracked at Head, the diff endpoint returns changed-file metadata for a Branch diff, and the project view returns all local and remote branch names. The change must remain compatible with `en-US` and `pt-BR`, introduce no external dependency, and preserve the existing rule that review scope and selected files alone determine what is analyzed.

## Goals / Non-Goals

**Goals:**

- Make the visible file universe match the user's immediate navigation need without changing review semantics.
- Default Branch diff to changed files and the other scopes to all tracked files.
- Support fast file lookup and equivalent flat and collapsible-tree views.
- Make all branch fields searchable through one accessible interaction model.
- Explain each project quality command succinctly in both supported locales.
- Keep large repository interactions responsive and avoid redundant tree requests.

**Non-Goals:**

- Changing `ReviewScope`, review request payloads, analyzer behavior, or Git comparison semantics.
- Persisting file-browser preferences across page loads or adding them to `UiConfig`.
- Adding fuzzy search, server-side branch search, branch creation, or branch refresh controls.
- Selecting or deselecting every file in a folder as a batch action.
- Adding a new backend endpoint or third-party UI dependency.

## Decisions

### 1. Keep navigation preferences independent from review state

Introduce local `FileUniverse` (`changed` or `all`) and `FileLayout` (`flat` or `tree`) state. File universe, layout, query, and collapsed folders only derive what is rendered; they never write to `reviewScope` or `selectedFiles` and are never sent to review APIs.

Changing scope resets the universe contextually: Branch diff selects `changed`, while Selected files and Whole project select `all`. The flat layout is the initial layout to preserve today's presentation. Layout remains stable while scope changes; the file query resets when scope, Base, or Head changes so an old filter cannot make a newly selected context appear empty.

Alternative considered: make `Changed` and `All` redefine the reviewed file set. Rejected because that duplicates and conflicts with the existing Scope control.

### 2. Load all-files, changed-files, and scoped-preview data by their actual dependencies

Split the current combined fetch into independently managed data:

- `tree(Head)` supplies all tracked paths and reloads only when the project or Head changes.
- `diff(Base, Head, branch_diff)` supplies the changed paths independently of the active scope.
- The existing scope-aware preview supplies metrics, patch rendering, and review estimation.

When the active scope is Branch diff, the branch preview is also the scope-aware preview and the request/result is reused. Other scopes may require the existing scoped preview plus a Branch diff preview so `Changed` remains truthful. Requests retain stale-response guards so a slow response cannot overwrite newer Base, Head, Scope, or selection state.

Alternative considered: add a lightweight changed-files endpoint. Rejected for this change because the capped diff response is already available and avoiding an API contract addition is worth the bounded extra payload. A dedicated endpoint can be introduced later if measurement shows a material cost.

### 3. Derive both layouts from one normalized file model

Build a memoized presentation model from the selected universe and a memoized `Set` of tracked and selected paths. Search uses trimmed, case-insensitive substring matching against both the full repository-relative path and its basename. The response order remains stable.

The tree is built from Git's `/`-separated paths. Directory node IDs use their full repository-relative directory path, so collapsed state remains unambiguous when folder names repeat. Search results include all ancestor directories and temporarily reveal matching descendants without mutating the user's collapsed-folder set. Individual and global expand/collapse controls affect folders only; file selection remains per-file.

Changed paths that are absent from the Head tree, such as deleted or untracked working-tree files, remain visible because they are part of the real Branch diff. In Selected files scope their checkboxes are disabled with an explanation because the existing selected-files snapshot accepts only paths tracked at Head.

Alternative considered: intersect changed paths with the Head tree. Rejected because it would hide legitimate diff content and make the navigation list disagree with the preview.

### 4. Extract focused accessible UI components

Extract the file browser, branch combobox, and tooltip into focused components rather than growing the existing `project-workspace.tsx` further. The repository inspector continues to own API state and review orchestration.

The branch component is controlled and accepts a label, current value, options, and `onChange`. It filters the already-loaded branch array locally, disallows free-form values, and implements button/input/listbox semantics with pointer selection, Arrow keys, Enter, Escape, focus restoration, and an explicit no-results state. Base, Head, and Default base branch use the same component.

The tooltip component places a focusable information trigger beside each quality-command label. Tooltip content is available by hover, keyboard focus, and tap/click; Escape and focus/pointer dismissal close it. The trigger and tooltip are connected with accessible naming/description attributes rather than relying on the browser `title` attribute.

Alternative considered: retain native selects and use an HTML datalist. Rejected because datalist behavior and validation vary across browsers and do not provide a consistent searchable listbox. Native `title` tooltips were rejected because they are not reliably available to touch and keyboard users.

### 5. Keep derived work bounded for large repositories

Memoize file-universe construction, search results, tree construction, and membership sets. Use a deferred query only when filtering/rendering is large enough to affect input responsiveness, and apply off-screen rendering containment to long rows. Avoid `Array.includes` inside every file row and avoid refetching the tracked tree after each selected-file checkbox change.

No virtualization dependency is introduced. The fixed-height scrolling panel, collapsed tree, deferred filter, set lookups, and rendering containment are sufficient for the first iteration and preserve simple keyboard navigation.

### 6. Route all new user-facing text through the locale helper

`ProjectQualityCommands` will use the existing UI text context, and all new labels, empty states, instructions, tooltip copy, and accessibility text will have English source strings and Brazilian Portuguese mappings. This change does not redesign the existing localization mechanism.

## Risks / Trade-offs

- **An extra Branch diff response may be fetched while another scope is active** → Reuse the same result in Branch diff, keep the existing transport cap, and measure before introducing a specialized endpoint.
- **A custom combobox has more accessibility surface than a native select** → Implement one shared component, follow the ARIA combobox/listbox interaction model, and verify keyboard, focus, pointer, and screen-size flows in a real browser.
- **Filtered or collapsed rows can conceal selected files** → Keep selection independent, display selected and visible counts, and never clear hidden selections implicitly.
- **Deleted or untracked changed files cannot be selected by Selected files scope** → Render them disabled with a concise explanation while leaving them available to Branch diff.
- **Rapid context changes can race asynchronous responses** → Key effects to their true dependencies and ignore or abort stale requests.
- **The active `friendly-error-messages` change may edit the same frontend files** → Keep this change separate and re-read/reconcile those files immediately before implementation.

## Migration Plan

This is an additive frontend change with no persisted-data or API migration. Implement reusable primitives first, integrate the quality form and repository inspector, add translations, then run typecheck, lint, build, and real-browser desktop/mobile accessibility flows. Rollback consists of restoring the native selects and existing flat tracked-file list; stored projects and reviews remain compatible.

## Open Questions

None. Product decisions for presentation-only behavior, contextual defaults, and coverage of all three branch selectors were confirmed during exploration.
