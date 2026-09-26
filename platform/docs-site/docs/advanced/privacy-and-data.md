---
id: privacy-and-data
title: Privacy and your data
sidebar_position: 2
slug: /privacy-and-data
---

RevAI has no account, no telemetry and no hosted storage. This page is the
whole picture of what leaves your machine.

## What leaves your machine

Only the review context sent to the provider you configured: the filtered
hunks or files, with detected secrets redacted before anything is sent.
Nothing else is transmitted, and choosing a local model server means nothing
leaves at all.

## What stays

Reviews, findings, configuration and your project list are files in your
home directory. Credentials live in their own file, separate from
everything else, and are excluded from exports.

```bash
~/.revai/
~/.revai/credentials.yaml
```

## Repository content is untrusted

Code under review is treated as data, never as instructions. A comment in a
file that tells the reviewer to ignore its rules is quoted, not obeyed.

## Taking your data out, or deleting it

Export everything as a portable archive from the data settings, or delete
the directory. There is no server-side copy to ask anyone about.
