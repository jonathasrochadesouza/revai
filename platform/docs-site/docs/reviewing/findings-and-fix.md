---
id: findings-and-fix
title: Findings and fixes
sidebar_position: 3
slug: /findings-and-fix
---

A finding names a file and a line range, explains itself, and — often —
carries a suggested patch.

## Triage

Mark each finding fixed, dismissed, or a false positive. The choice is
stored with the review, so the insights screen can tell a real problem from
noise over time.

## Applying a suggested patch

A patch is applied to your working tree, always unstaged and never
committed. RevAI refuses when the active branch differs from the review's
head or when the file changed since the review, validates the patch first,
and re-runs the analyzer that produced the finding afterwards. If the rule
still fires, the change is reverted.

```bash
revai fix . --review <review-id> --finding <finding-id> --dry-run
revai fix . --review <review-id> --finding <finding-id>
```

## When there is no patch

Generating a fix asks the configured model for a minimal edit, converts it
into a real diff, and applies it through the same validation. It costs
tokens, so it is always an explicit action.

```bash
revai fix . --review <review-id> --finding <finding-id> --generate
```

## Review before committing

Everything lands unstaged on purpose: read the diff yourself before
committing. RevAI never commits, never pushes, and never touches a branch.

```bash
git diff
```
