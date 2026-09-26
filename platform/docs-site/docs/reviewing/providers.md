---
id: providers
title: Choosing a provider
sidebar_position: 1
slug: /providers
---

A review runs with exactly one configured provider. RevAI supports hosted
APIs and local CLI agents, and probes both without spending tokens.

## Hosted APIs

Store a key and RevAI verifies it with a zero-token request. Keys are
written to a credentials file separate from your projects and are never
returned by any endpoint — only a masked form is ever displayed.

## Local CLI agents

These reuse the sign-in you already have in the agent, so there is no key to
store. RevAI resolves the binary, reports the absolute path it found, and
runs a read-only agent with tool inheritance disabled.

## What the states mean

The terms below are the literal state values the API reports, so they stay
untranslated: a user matching a badge to this list needs them verbatim.

- **`ready`** — Installed or reachable, and authenticated. Safe to run a review.
- **`needs_auth`** — Present but not signed in, or missing a key.
- **`unknown`** — Present, but its sign-in state cannot be determined without
  spending a request. One agent genuinely cannot answer this, so RevAI says
  so instead of guessing.
- **`not_found`** — Not installed, or not on your PATH.
- **`error`** — Present but misbehaving — a crash, a timeout, or output it
  could not parse.

## Staying entirely local

Point RevAI at a model server running on your own machine and no code leaves
it at all. Quality depends on the model you pull, but the deterministic
analyzers run either way.
