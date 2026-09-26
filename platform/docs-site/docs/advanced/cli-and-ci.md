---
id: cli-and-ci
title: CLI and CI
sidebar_position: 1
slug: /cli-and-ci
---

The installed CLI runs the same read-only pipeline without a web server,
which is what makes RevAI usable in continuous integration.

## Reviewing from the terminal

Point it at a repository, name the base and head, and choose the mode.
Selected-file and whole-project scopes are available too.

```bash
revai review . --base main --head feature/payments \
  --mode both --model claude-haiku-4.5 \
  --format sarif --output revai.sarif --fail-on medium
```

## Exit codes

Zero means the run finished under your threshold. One means the configured
finding threshold was reached — the signal a pipeline should fail on. Two
means a configuration or execution error, which is a different problem and
deserves a different alert.

```text
0  under threshold
1  threshold reached
2  configuration or execution error
```

## Report formats

JSON for machines, Markdown for a pull request comment, a standalone HTML
file that opens anywhere, and SARIF for code-scanning integrations.

```bash
--format json | md | html | sarif
```

## In a pipeline

Provide the provider key as a secret, pick a cheap model, and scope the
review to the branch diff. Fail the job on the exit code rather than parsing
the report.
