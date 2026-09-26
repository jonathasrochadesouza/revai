---
id: getting-started
title: Getting started
sidebar_position: 1
slug: /getting-started
---

RevAI reviews code on your machine. Repositories are never uploaded: only the
filtered, secret-redacted context a review needs reaches the model provider
you configure.

## The two pieces

A local API does the work and owns your configuration, and a web app talks to
it. Both run on your machine, and the CLI runs the same pipeline with no web
server at all.

```bash
cd platform/api && uv run revai-api
cd platform/web && npm run dev
```

## Your first run, in order

1. Start the backend and confirm the connection screen is green.
2. Choose a provider and store its key, then verify it.
3. Open a local Git folder, or clone a repository.
4. Check the diff preview and its cost estimate, then run the review.

## Where things are kept

Reviews, configuration and masked credential metadata live under your home
directory. Credentials are stored separately from repositories, and nothing
is sent anywhere without an explicit action.

```bash
~/.revai/config.yaml
~/.revai/credentials.yaml
~/.revai/reviews/
```
