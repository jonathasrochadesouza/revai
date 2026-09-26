---
id: first-review
title: Running a review
sidebar_position: 2
slug: /first-review
---

Reviews are deliberate: you pick what is reviewed, see what it will cost, and
then run it.

## Three scopes

- **Branch diff** — everything that changed between a base and a head
  branch. The default, and the one that matches a pull request.
- **Selected files** — a handful of files you choose in the browser.
- **Whole project** — the full tree. Expensive, so reserve it for a first
  assessment.

## Static, AI, or both

Deterministic analyzers run first and cost nothing: linters, a secret
scanner, and a structural pass. The AI pass then judges only what deserves
judgement. Running both is the point of the product.

## The cost estimate

Before anything is sent, RevAI estimates tokens and price. Above your
warning threshold it asks for confirmation; above your hard budget it
refuses. Both live in the engine settings.

## While it runs

Each stage reports as it completes, and the job survives closing the browser
tab because it belongs to the local process, not the page. Cancelling stops
it at the current stage.
