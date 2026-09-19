## 1. Shared Accessible Controls

- [x] 1.1 Implement a reusable UI tooltip with hover, focus, tap/click, Escape, dismissal, accessible trigger/tooltip association, and no dependency on the native `title` attribute.
- [x] 1.2 Implement a controlled searchable branch selector that filters supplied options case-insensitively, rejects free-form values, and supports pointer, touch, Arrow keys, Enter, Escape, active-option state, and focus restoration.
- [x] 1.3 Replace the Base, Head, and Default base branch native selects with the shared branch selector while preserving their existing update and review-cancellation behavior.

## 2. Review File Browser

- [x] 2.1 Add typed, memoized file-browser helpers for tracked/changed membership sets, basename/full-path search, stable visible-file derivation, and `/`-separated folder-tree construction with full-path directory IDs.
- [x] 2.2 Build the file browser with `Changed`/`All` universe controls and counts, a case-insensitive search field with distinct empty states, and presentation state that never mutates review scope or selected files.
- [x] 2.3 Add flat and collapsible-tree layouts over the same searched file set, including per-folder and expand-all/collapse-all controls plus temporary ancestor disclosure during search.
- [x] 2.4 Preserve selected files when rows are filtered or collapsed, display visible and selected counts, replace row-level array membership scans with sets, and disable changed paths not tracked at Head in Selected files scope with an accessible explanation.
- [x] 2.5 Add responsive and large-list rendering safeguards, including deferred expensive filtering where warranted and off-screen rendering containment without introducing a virtualization dependency.

## 3. Repository Inspector Data Flow

- [x] 3.1 Decouple tracked-tree loading from preview loading so the tree depends only on project and Head and is not refetched for scope or selected-file changes.
- [x] 3.2 Load and retain a Branch diff preview independently from non-branch scoped previews, reusing one request/result when Branch diff is active and guarding every asynchronous result against stale Base, Head, Scope, and selection state.
- [x] 3.3 Apply contextual universe defaults (`Changed` for Branch diff, `All` for Selected files and Whole project), preserve layout across scope changes, and clear file search when Scope, Base, or Head changes.
- [x] 3.4 Verify that universe, search, layout, and folder actions never alter the scope or selected-file payload passed to preview and review APIs.

## 4. Quality Guidance and Localization

- [x] 4.1 Add the reusable tooltip to Checkstyle, Tests, and Build labels with concise explanations of Java style/static rules, test-suite regressions, and compilation/packaging validation respectively.
- [x] 4.2 Route the Project quality commands section and every new file-browser, branch-search, tooltip, empty-state, count, disabled-state, and accessibility string through the existing UI text helper.
- [x] 4.3 Add and review Brazilian Portuguese mappings for all new English source strings, including screen-reader-only instructions and control labels.

## 5. Verification

- [x] 5.1 Run frontend typecheck, lint, and production build and resolve all regressions without changing backend contracts or adding runtime dependencies.
- [ ] 5.2 Exercise Branch diff, Selected files, and Whole project with different and identical Base/Head refs, verifying contextual defaults, all-versus-changed membership, working-tree/untracked behavior, deleted-path handling, hidden selection preservation, counts, and review payload invariance.
- [ ] 5.3 Perform real-browser keyboard, pointer, touch-sized/mobile, dark/light theme, and `en-US`/`pt-BR` checks for both file layouts, all branch selectors, search/no-results states, folder controls, disabled changed paths, and quality-command tooltips.
- [x] 5.4 Reconcile any overlapping edits from the active `friendly-error-messages` change, inspect the final working-tree diff for scope containment, and rerun the affected verification commands.
