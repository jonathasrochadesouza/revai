# Phase 6 — Results: findings, diff, and patch handling

> ✅ Complete and verified (initial delivery shipped inside the review
> workspace; findings/diff components extracted and given a split view in the
> market-readiness pass — see CHANGELOG [Unreleased]).

Goal: turn a finished review into something a developer can act on — a ranked
finding list with decisions, a readable diff of what was reviewed, and patch
handling that never applies anything automatically.

## Scope delivered

- **Ranked findings list.** Findings are sorted by severity then descending
  confidence (`Review.sorted_findings`), with severity chips, file:line
  anchors, source labels and per-finding status
  (`platform/api/revai/domain/models.py`, rendered by
  `platform/web/src/components/findings/finding-card.tsx`).
- **Per-finding decisions.** `PATCH
  /api/projects/{id}/reviews/{review_id}/findings/{finding_id}` transitions a
  finding to `fixed`, `false_positive`, or `dismissed`, appending an auditable
  `FindingDecision` with reason and timestamp.
- **Evidence expansion.** Rationale ("why this matters") and the suggested
  patch are one click away, never noise by default.
- **Patch copy, never auto-apply.** A suggested patch is copied to the
  clipboard; the backend validates that provider prose only counts as a patch
  if it matches the finding's file (`_validated_finding` in
  `pipeline/ai.py`), and anything else is stored as prose with no patch.
- **Diff of the reviewed change.** `DiffViewer`
  (`platform/web/src/components/diff/diff-viewer.tsx`) renders the unified
  diff with a **unified / split toggle**; the split view parses the patch into
  (old, new) row pairs with tracked line numbers (pure functions
  `parseUnifiedPatch` / `toSplitRows`, unit-tested).
- **Live progress.** While the review streams, stage and analyzer events show
  what is running; a failed run surfaces its structured error key through the
  friendly-error catalog.
- **History.** The last 8 runs are listed inline for comparison and retry.

## Deliberately out of scope (documented, tracked on GitHub)

- **Split diff with per-line patch application** — applying hunks is a change
  to the user's working tree, which the product intentionally refuses to do
  automatically; see the deferred-fallback and no-auto-apply decisions in
  `ARCHITECTURE.md`.
- **Cross-review finding comparison UI** — the compare API exists
  (`/reviews/compare/{left}/{right}`); surfacing it in the workspace is future
  work tracked on GitHub.
