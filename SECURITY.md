# Security Policy

## Supported versions

Only the latest release (and `main`) receives security fixes.

## Reporting a vulnerability

Do **not** open a public issue for a suspected vulnerability.

- Email **security@revai.local** (placeholder — replace with the maintainer's
  real address before the first public release) or open a private security
  advisory via GitHub's "Security → Advisories" tab.
- Include reproduction steps, affected component (api / web / cli), and the
  `revai doctor --json` output where relevant.
- Expect an initial response within 7 days.

## Threat model, by design

RevAI is a **single-user, local-first tool**. These are deliberate decisions,
documented in `platform/docs/ARCHITECTURE.md`:

- The API binds to `127.0.0.1` only, with loopback-restricted CORS and **no
  authentication**. Deploying it beyond loopback is unsupported and unsafe;
  the Docker Compose file publishes ports on loopback only.
- The web UI and the API trust each other because they are the same local
  process boundary; CORS is restricted to explicit loopback origins.
- Repository content is treated as **adversarial data** in AI prompts: a
  fixed anti-injection boundary wraps the user prompts server-side and cannot
  be removed by prompt customisation (see
  `platform/api/revai/domain/prompts.py` and the tests in
  `platform/api/tests/test_pipeline_safety.py`).
- Secrets live in `credentials.yaml` (chmod 600) and are redacted before
  chunks reach any provider (`revai/pipeline/safety.py`); no secret is ever
  included in an API response or persisted event.

If you run RevAI in a way that exposes these assumptions (reverse proxy,
shared host, remote access), you are on your own.
