---
id: run-the-backend
title: Starting the backend
sidebar_position: 2
slug: /run-the-backend
---

The web app talks to a local API. When that API is not answering, every
screen that needs data says so and this page is the fix.

## Two local processes, no containers

Install the dependencies and run the API directly. Reviews need direct
access to your Git repositories on disk — running the backend inside Docker
breaks that, since the container cannot see your projects, mounted paths, or
local CLI tools.

```bash
cd platform/api
uv sync --all-groups
uv run revai-api
```

The API answers on its health endpoint once it is ready. If it does not, run
the doctor command for a storage and configuration diagnostic.

```bash
curl http://127.0.0.1:8799/api/health
uv run revai doctor
```

## The address and the port

The API listens on loopback only, so nothing outside your machine can reach
it. The web app expects it at the address shown on the API & AI screen;
override it with an environment variable if you moved it.

```bash
http://127.0.0.1:8799
NEXT_PUBLIC_API_URL=http://127.0.0.1:8799
```

## When it still will not start

Read the logs first — a port already in use and a failed dependency install
look nothing alike. The API & AI screen also offers a copyable
troubleshooting prompt you can paste into a coding agent, with the captured
error already in it.
