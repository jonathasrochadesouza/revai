# Phase 2 — Providers & detection

> **Status:** ✅ complete and verified · 2026-07-28

The goal: know, honestly, which engines this machine can actually use — before a
review is started and before a single token is spent.

Almost every design decision in this phase came from **measuring the real CLIs on a
real Windows machine**, not from reading their documentation. The measurements
contradicted the documentation more than once, and one of them only surfaced because
I called the running server instead of trusting a green test suite.

---

## Try it

```bash
# terminal 1
cd platform/api && uv run revai-api

# terminal 2
cd platform/web && npm run dev
```

Open <http://localhost:3000/settings/engine> and look at **Detected providers**.

```bash
# or, without the UI
curl http://127.0.0.1:8799/api/providers
curl -X POST http://127.0.0.1:8799/api/providers/openrouter/verify
```

---

## What was built

### Contracts — `revai/providers/base.py`

One `Protocol` covers hosted APIs and local CLI agents, so the pipeline consumes
either without branching.

**`HealthState` has five members, not two.** "Is it usable?" genuinely has more than
two answers:

| State | Meaning |
|---|---|
| `ready` | Installed/reachable and authenticated |
| `needs_auth` | Present, but not signed in or missing a key |
| `unknown` | Present, and its auth state **cannot be determined** without spending money |
| `not_found` | Not installed, or not on `PATH` |
| `error` | Present but misbehaving — crash, timeout, unparseable output |

`unknown` is not a placeholder for laziness. It is the only truthful answer for
GitHub Copilot CLI, which ships no auth-status command and returns exit code 0 for
invalid input.

`ProviderEvent` is a discriminated union — `started | delta | usage | finished |
failed` — so streaming is exhaustively handled at the type level rather than by
inspecting dictionaries.

`UsageStats.cost_usd` is `float | None`, and `None` means *not reported*. A `0.0`
default would be a lie the user only discovers on their invoice.

### Detection — `revai/providers/detection.py`

`CliSpec` describes each agent CLI declaratively: executables, version args, auth
args, whether auth output is JSON, install and login hints, and **aliases** — because
`kiro` and `kiro-cli` are different programs and users conflate them.

### Adapter — `revai/providers/api/openrouter.py`

Chosen first deliberately: it is OpenAI-compatible, so it doubles as the base for
the OpenAI adapter, and one key reaches every frontier model, which is the shortest
path to a usable product.

`health()` calls `GET /key`, which validates the key and returns the remaining
credit **without consuming tokens**. `analyze()` streams SSE with
`"usage": {"include": true}` so real cost comes from the provider rather than from a
local estimate.

### API — `revai/api/routes/providers.py`

```
GET  /api/providers                    → every provider, probed concurrently
POST /api/providers/{id}/verify        → re-probe one
```

Two properties hold:

* **Probing never fails the request.** A broken provider is data to render, not an
  error. `verify` returns **200** with an unhealthy body — "I checked, and it is not
  working" is a *successful* check.
* **A probe never spends money.**

### Frontend — `components/provider-panel.tsx`

A client component that fetches after mount rather than blocking the server render:
probing spawns three subprocesses, and `copilot` alone takes over a second to start.
Filtered to `kind === "cli"` — the panel's whole premise is "what did we find
installed?", and a hosted API has nothing to find (see review point 2 below).

Every card shows the state pill, the version, **the absolute resolved path**, the
detail, and the exact command that would fix it. The path is not decoration — "not
found" and "found the wrong one" look identical until you can see which file was
resolved.

### Frontend — `components/ui/number-control.tsx`

Every numeric field in the budget card (spend cap, warning threshold, context
tokens, timeout) routes through this instead of a bare `<input type="number">`,
because that naive version has a bug users hit immediately: `Number("") === 0`, so
clearing a field to retype it silently commits a zero. See review point 1 below for
the full story and how it was verified.

---

## What the real CLIs actually do

Measured on this machine. Each finding forced a change in the implementation.

| # | Measurement | Consequence |
|---|---|---|
| 1 | `create_subprocess_exec("copilot")` → `FileNotFoundError [WinError 2]`, because `copilot` is a `.BAT` shim | Every invocation resolves through `shutil.which` first and passes the absolute path |
| 2 | `copilot --version` prints **2** lines (version + update notice); `kiro --version` prints **3** (version, git hash, arch) | Version is extracted by regex, never taken as the whole of stdout |
| 3 | `copilot whoami` → **exit 0**, error only on stderr | Exit code alone cannot decide health; stderr is inspected too |
| 4 | `copilot --definitely-not-a-flag` → **never returned** | Hard timeout plus `stdin=DEVNULL` on every call |
| 5 | `kiro` → `C:\Dev\Bins\Kiro\bin\kiro.CMD` (the **IDE**, 0.12.333); `kiro-cli` → `kiro-cli.EXE` (the **agent**, 2.14.1) | `kiro-cli` is the executable; `kiro` is only an alias used to explain the near miss |
| 6 | `kiro-cli whoami --format json` → `{"account":null}` with **exit 1** when signed out | JSON is parsed; exit code is not the signal |
| 7 | This machine's `GITHUB_TOKEN` holds a classic PAT, which Copilot rejects outright | Recorded as a documented failure mode, not silently swallowed |

### The version regex

Three details are load-bearing, each pinned by a test:

```python
_SEMVER = re.compile(r"(?:^|[^\w.])v?(\d+\.\d+(?:\.\d+)?(?:[-+][A-Za-z][\w.]*)?)")
```

* `(?:^|[^\w.])` — rejects a preceding word character, so `abc1.2.3` yields nothing
  instead of a misleading `2.3`. Rejecting a preceding dot stops `.windows.1` being
  read as a version of its own.
* `v?` outside the capture — `v3.4` matches but reports `3.4`. A `\b` here **cannot
  work**: `v` and `3` are both word characters, so no boundary exists between them.
* `[-+][A-Za-z]` — a prerelease must start with a letter, so `1.2.3-beta.1` stays
  whole while `git version 2.54.0.windows.1` still yields `2.54.0`.

No trailing anchor, because `copilot` prints `1.0.69.` with a full stop.

I did not pick this by reasoning alone — I ran all ten cases against both candidate
patterns and compared. The chosen one fixed `v3.4` **and** a pre-existing false
positive I had not noticed.

---

## The bug a green test suite hid

`GET /api/providers` returned **500** from the real server while all 158 tests
passed:

```
File "asyncio/base_events.py", line 528, in _make_subprocess_transport
    raise NotImplementedError
```

**uvicorn installs `WindowsSelectorEventLoopPolicy`, and a selector event loop cannot
spawn subprocesses at all.** pytest-asyncio runs on the *proactor* loop, so the
entire suite exercised a code path that production never uses.

Reproduced in isolation before fixing anything:

```
selector loop + create_subprocess_exec -> NotImplementedError (bug reproduced)
```

**Fix:** `subprocess.run` on a worker thread via `asyncio.to_thread`. This works on
every loop implementation, and three short-lived threads is a trivial cost for a
probe that runs on demand.

**Regression test:** `test_run_command_works_on_a_selector_event_loop` builds an
explicit `asyncio.SelectorEventLoop` and is deliberately **synchronous**, so the
ambient pytest-asyncio loop cannot be substituted for the one that actually breaks.
Verified it fails against the old implementation.

The lesson is uncomfortable and worth writing down: **a green suite is evidence about
the suite, not about the product.** Nothing short of calling the running server would
have found this.

---

## Decisions worth defending

**`unknown` counts as usable.** Refusing to run would make Copilot CLI *permanently*
unusable, since it has no way to report auth state. Attempting and surfacing a real
error is strictly better than a guess dressed up as a refusal.

**`adapter_ready` is separate from `state`.** A CLI can be installed and signed in
while RevAI still cannot drive it. "Installed" and "usable" are different claims, and
collapsing them would promise something the product does not yet deliver.

**Planned providers are listed, not hidden.** The roadmap belongs in the product, not
only in the docs. The backend reports them as `not_found` because the enum has no
"unimplemented" member — but the UI renders **Planned** and suppresses both the *Fix*
line and the *Test* button, because a hosted API cannot be installed and there is
nothing for the user to do.

**Probes are concurrent.** Three CLI probes at a 20-second ceiling each would
otherwise block a request for a minute.

**Verify updates one card, not the whole panel.** Re-running the full sweep would
restart every subprocess and blank the list for a second, which reads as a bug.

**The effect subscribes, it does not `setState` synchronously.** ESLint's
`react-hooks/set-state-in-effect` is right on the substance: state is set from the
promise callbacks, with a `cancelled` guard so a late response cannot land on an
unmounted component.

---

## Test suite speed

The suite reached **2 min 54 s**, because tests were spawning real CLI subprocesses
and one made a live network call. A three-minute suite stops being run, which
undermines the verification discipline this project depends on.

* A `cli` marker plus `addopts = "-m 'not cli'"` excludes real-CLI integration by
  default. It is still one command away: `pytest -m cli`.
* CLI detection is faked in route tests with the **states measured on this machine**,
  so the fakes assert real behaviour rather than convenient behaviour.
* `httpx.MockTransport` replaces the live OpenRouter call.

**Result: 2 min 54 s → 20–35 s.** Machine-independent, and the integration test still
passes on demand.

That range is honest rather than a rounding: wall-clock varied from 20 s to 105 s
across runs, so I measured instead of guessing. `--durations` shows the tests
themselves sum to roughly 17 s and are dominated by the phase-1 Hypothesis property
tests (6.3 s and 5.4 s), which hammer the disk. The spread is contention on this
machine, not remaining subprocess cost — the slowest detection test is 0.55 s, and
that one is *deliberately* slow because it asserts the timeout fires.

---

## Verification performed

| Check | Result |
|---|---|
| `pytest` (default) | **162 passed**, 1 deselected, 20–35 s |
| `pytest -m cli` (real CLIs) | **1 passed** against the real machine |
| `ruff check` + `ruff format --check` | clean |
| `tsc --noEmit` | clean |
| `eslint` | clean |
| `next build` | compiled successfully |
| `npm audit --omit=dev` | 0 vulnerabilities |
| Live `GET /api/providers` | 200, 8 providers, real states |
| Live `POST /.../verify` | 200 even when unhealthy |
| Live probe, **invalid** key stored | real 401 → `needs_auth`, "OpenRouter rejected the key." |
| Live probe, key removed | `needs_auth`, "No API key stored." |
| Selector event loop | subprocess launches (regression covered) |
| Browser: panel renders | all 8 cards, correct pills, paths, fixes |
| Browser: **Test** button | request issued, card updated in place |
| Secret leakage | asserted absent from the full provider response |

### States detected on this machine

```
openrouter   api  needs_auth              adapter_ready=true
anthropic    api  not_found  → "Planned"  adapter_ready=false
openai       api  not_found  → "Planned"  adapter_ready=false
gemini       api  not_found  → "Planned"  adapter_ready=false
ollama       api  not_found  → "Planned"  adapter_ready=false
claude_code  cli  not_found               adapter_ready=false
copilot_cli  cli  unknown     1.0.69      adapter_ready=false
kiro_cli     cli  needs_auth  2.14.1      adapter_ready=false
```

---

## Deliberately not done

**No CLI adapter yet.** Detection tells you a CLI is present; *driving* it — session
persistence, tool permissions, parsing its cost accounting — is phase 8. Reporting
`adapter_ready: false` keeps that honest instead of shipping a button that fails.

**No live model list.** `web/src/lib/models.ts` is still the offline catalogue.
Refreshing it from `GET /api/v1/models` is a small, separate change.

**No retry or circuit breaker.** Adding one before there is a pipeline to protect
would be speculative. The failure taxonomy in
[`DEFERRED-FALLBACK-PROVIDER.md`](DEFERRED-FALLBACK-PROVIDER.md) already establishes
that most failures must **not** be retried elsewhere.

---

## Review feedback applied

Four points raised after the first pass, all addressed and re-verified live against
the running backend.

**1. A real bug: saving the budget could fail with no value the user had typed.**
Clearing a number field to retype it silently wrote `0`, because
`Number("") === 0` in JavaScript. `0` is not a legal budget, so the backend rejected
it with `Input should be greater than 0` — a validation error about a value the user
never entered. Fixed by `components/ui/number-control.tsx`, which treats the field as
*text* and only commits a value once it actually parses as a number; an empty field
mid-edit commits nothing, and blurring it empty snaps back to the last good value.
Verified in the browser: cleared the field, retyped `1.25`, saved, and confirmed
`max_spend_usd: 1.25` in `config.yaml`; separately cleared it and blurred without
retyping, and it reverted to `1.25` rather than saving `0`.

**2. Detected providers narrowed to CLI agents only.** Hosted API providers
(OpenRouter, Anthropic, OpenAI, Gemini, Ollama) have nothing to *detect* — there is
no binary on `PATH`, only a key to store, and that is already the credentials card
above. Listing them in a panel titled "Detected providers" implied there was
something to find. The panel now filters to `kind === "cli"`, so it shows exactly
the three agent CLIs. Confirmed in the browser: the panel lists Claude Code, GitHub
Copilot CLI and Kiro CLI only, with no API providers.

**3. A loading state that does not imply a duration it cannot promise.** The
original skeleton mimicked eight card-shaped placeholders sized for a duration it
could not know in advance — `copilot` alone takes over a second to start. Replaced
with a single centred spinner that stays visible for exactly as long as detection
actually takes, with no fake structure to be wrong about.

**4. `$` shown as a currency prefix.** "Max spend per review" and "Warn above" are
US dollars, and a bare number looks like the user's local currency by default.
`NumberControl` renders a fixed `$` inside the field, alongside the existing `USD`
suffix.
