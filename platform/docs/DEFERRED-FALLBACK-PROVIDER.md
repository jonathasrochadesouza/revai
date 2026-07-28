# Deferred: provider fallback

> **Status:** designed, deliberately **not implemented**.
> Removed from the Settings UI on 2026-07-28. This document preserves the reasoning
> so it can be picked up later without rediscovering it.

---

## What it was

A second provider, configured alongside the primary, used automatically when the
primary fails. The idea came from mock 01's "fallback API key".

It was built into phase 1 as two fields — `fallback_provider_id` and
`fallback_model` — and then taken out of the interface before phase 2.

## Why it was deferred

Not because it lacks value, but because a naive version is worse than none.

**1. It makes cost and quality unattributable.** RevAI's central claim is that you
can see exactly what a review cost and which model produced each finding. A fallback
that switches silently mid-run breaks that: two findings in the same report may come
from different models at different prices, with nothing recording which was which.
Fixing that means per-finding provenance and per-provider cost accounting — real work
that belongs with the metrics phase, not bolted on beforehand.

**2. "Failure" is not one thing.** Retrying the wrong class of error is actively
harmful:

| Failure | Correct response | Why |
|---|---|---|
| Network timeout, 502, 503 | Retry on the same provider | Transient; switching loses prompt cache |
| 429 rate limit | Back off, then retry same | The provider told you when to return |
| 401, 403 | **Fail loudly** | A fallback hides a misconfigured key indefinitely |
| Context length exceeded | Re-chunk, then retry | A different model has the same limit |
| Content filter | **Do not fall back** | Likely to repeat, and masks a real signal |
| Provider outage, 5xx sustained | **Fall back** | The only case that genuinely warrants it |
| Budget exceeded | **Never fall back** | The user set a cap; spending elsewhere defies it |

Only one row justifies switching providers. Without this taxonomy a fallback mostly
converts loud, fixable errors into quiet, expensive ones.

**3. It multiplies the cost ceiling.** `max_spend_usd` is a per-review cap. A
fallback that re-runs work spends the budget twice unless the guard tracks cumulative
spend across attempts — so the budget model has to change first.

**4. There is nothing to fall back to yet.** Phase 2 ships one adapter, OpenRouter.
A fallback needs two working providers to be meaningful, which is phase 10.

**5. OpenRouter already does this, better.** It has provider routing built in: one
model id can be served by several upstreams with automatic failover, priced and
reported as a single request. For the primary path, using that is strictly better
than reimplementing it one layer up.

## What a correct implementation needs

### Configuration

```yaml
engine:
  mode: api
  provider_id: openrouter
  model: anthropic/claude-sonnet-4.5

  fallback:
    enabled: true
    provider_id: anthropic
    model: claude-sonnet-4-5

    # Only these classes trigger a switch.
    on: [provider_outage, sustained_5xx]

    # Attempts on the primary before switching.
    retries_before_switch: 2

    # Cumulative across primary and fallback, not per attempt.
    respect_budget: true

    # Refuse rather than silently downgrade quality.
    require_structured_output: true
```

### Domain changes

- `Finding.provider_id` and `Finding.model` — provenance per finding, not per review.
- `ReviewStats.attempts: list[AttemptStats]` — one entry per provider used, each with
  its own tokens and cost, so the total is explainable.
- `FailureClass` enum matching the taxonomy table above.
- `Review.degraded: bool` plus `degraded_reason` — the report must say when it was
  not produced by the configured engine.

### Provider layer

- `classify_failure(exc) -> FailureClass` in `providers/base.py`, implemented per
  adapter, since every provider signals rate limits and outages differently.
- A retry policy object rather than inline `try/except`, so the behaviour is testable
  without a live provider.
- A circuit breaker: after N consecutive primary failures, skip straight to the
  fallback for a cooldown window instead of paying the timeout every time.

### Pipeline

- The budget guard must track spend **across** attempts and abort mid-fallback if the
  cap is reached.
- Emit an explicit `provider_switched` event to the event stream. A silent switch is
  the failure mode this whole design exists to avoid.

### UI

- The fallback selector returns, but only offering providers that have a stored
  credential and a ready adapter — an unreachable fallback is worse than none.
- A **degraded** badge on any review that used the fallback, and the reason shown on
  hover.
- Insights should separate cost by provider once more than one can appear in a run.

### Tests

- One test per row of the failure table, asserting switch or no-switch.
- A property test: cumulative spend across attempts never exceeds `max_spend_usd`.
- A test that a `401` never triggers a fallback, because that is the mistake most
  likely to be introduced by a later refactor.

## Migration already handled

`EngineConfig` sets `extra="ignore"` so a `config.yaml` written by the earlier build,
containing `fallback_provider_id` and `fallback_model`, still loads. The keys are
dropped on the next save. No user action is required, and nothing breaks.

## When to revisit

After **phase 10**, when at least two adapters are production-ready and per-provider
cost accounting exists. Until then, OpenRouter's own provider routing covers the case
that actually matters.
