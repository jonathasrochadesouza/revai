# Phase 1 — Storage & configuration

> **Status:** ✅ complete and verified · 2026-07-28

The goal: make configuration durable, and prove that plain YAML is a defensible
choice as the datastore. Everything now survives a restart, and a failed write can
never leave a corrupt file behind.

---

## Try it

```bash
# terminal 1
cd platform/api && uv run revai-api

# terminal 2
cd platform/web && npm run dev
```

Open <http://localhost:3000/settings/engine>, change something, press
**Save to config.yaml**, then look at `~/.revai/config.yaml`.

---

## What was built

### Domain — `revai/domain/`

`enums.py` holds the closed vocabularies as `StrEnum`, so they serialise to readable
YAML scalars and still validate on the way back in. `SCHEMA_VERSION` lives here and
is stamped on every persisted document.

`models.py` is the single source of truth for every shape that crosses a boundary.

**`Finding` gains five fields the legacy JSON never had:**

| Field | Why it was missing before mattered |
|---|---|
| `id` | Nothing could be referenced, which is why the old report renders `Branch undefined` |
| `category` | Orthogonal to severity — needed for the metrics breakdown |
| `source` | Which stage found it, so the merge stage can rank by confidence |
| `confidence` | Ordering and noise filtering |
| `suggested_patch` | A unified diff, returned but never applied automatically |

`ReviewStats` separates cost from token counts and carries `cost_is_estimated`,
because CLI providers report tokens unreliably and some report no cost at all. The
UI can then say "estimated" instead of presenting a guess as a fact.

### Storage — `revai/storage/`

`base.py` defines `Repository` and `DocumentRepository` as `Protocol` classes, not
base classes. An implementation only has to match the shape, which is what keeps a
future Mongo backend from inheriting anything from the YAML one.

`yaml_store.py` provides three guarantees:

1. **A write never leaves a half-written file.** Serialise → temp file *in the same
   directory* → `os.fsync` → `os.replace`. Same directory matters: a cross-device
   move is a copy, and a copy is not atomic.
2. **Concurrent writers serialise** through a `filelock` sidecar. The API is single
   process today, but the reload worker, a future CLI and the user's own editor can
   all reach the same file.
3. **Comments and key order survive** — `ruamel.yaml` in round-trip mode, so a
   config a human annotated stays annotated after the app saves it.

`repositories.py` wires the four concrete repositories. Reviews are partitioned by
project, so deleting a project is a directory removal and one project's history
never slows down listing another.

### API — `revai/api/`

```
GET    /api/config              → config + path + exists
PUT    /api/config              → atomic replace, server-stamped updated_at
GET    /api/credentials         → masked previews only
PUT    /api/credentials         → store or replace
DELETE /api/credentials/{id}    → 204, or 404 when absent
```

`deps.py` is the injection seam. Repositories are constructed per request — they
hold nothing but a path — so overriding `get_settings` in a test redirects every one
of them at once.

### Frontend — `platform/web`

`/settings/engine` implements the concepts approved from the mocks:

- **Model API ⇄ Local CLI agent** selector (mock 07), re-skinned so the active card
  is marked by a near-black border rather than a coloured glow
- **Fallback provider** (mock 01)
- **Save to config.yaml** action bar (mock 07), sticky, naming the real file
- Deterministic-stage toggles with the tool each one shells out to

New primitives: `Switch` (a real `role="switch"` button, not a styled checkbox),
`Button`, `Field`/`TextInput`/`Select`/`NumberInput`.

---

## Decisions worth defending

**The whole document is saved in one PUT, not patched field by field.** This mirrors
how the backend writes the file: either the new configuration lands completely or
the previous one is untouched. A half-applied configuration is the one state that
would be genuinely confusing to debug.

**`extra="forbid"` on every model.** These files are hand-editable, so a typo like
`engien:` must be an error rather than a silently ignored key.

**A malformed config returns 422, not 500.** The message names the offending field,
because the user is the one who will fix it.

**Identifiers are validated against a filename allow-list** before touching the
filesystem. Ids are generated internally but they also arrive from URL path
parameters, so this is the last line of defence against traversal.

**Secrets never appear in a response.** Routes return `masked()`; the raw key is
only ever accepted, never echoed. Verified by asserting the secret's absence from
the full response text.

---

## Verification performed

| Check | Result |
|---|---|
| `pytest` | **87 passed** |
| `ruff check` + `ruff format` | clean |
| `tsc --noEmit` | clean |
| `eslint` | clean |
| `next build` | succeeded, `/settings/engine` present |
| `npm audit --omit=dev` | 0 vulnerabilities |
| Live `PUT /api/config` → reload | value persisted to disk |
| Live `PUT /api/credentials` | secret absent from response, present in file |
| Invalid budget via HTTP | 422 with a field-level message |
| Browser: change → save | "Saved to config.yaml", value confirmed in the file |
| Browser: reload | saved value returned from disk |
| Browser: invalid budget | inline warning **and** backend 422 surfaced |
| Browser: discard | reverts to the last saved state |

### Property-based tests

Three properties assert the guarantees that justify YAML over a database:

- **Round-trip fidelity** — 120 generated documents with unicode, floats, nesting
  and empty containers all return identical.
- **Atomicity** — after every write the file equals exactly one complete payload,
  never a prefix and never a blend of two.
- **No accumulation** — repeated writes leave exactly one file, no temp leftovers.

---

## What Hypothesis found

Three findings, and one of them was a genuine bug in my own code.

### A real bug: unencodable content returned 500

Hypothesis generated `'\ud800'` — a lone surrogate — and `atomic_write` raised a bare
`UnicodeEncodeError`. I checked whether that was actually reachable rather than
dismissing it as a synthetic input, and it is:

```
pydantic accepts lone surrogate: '\ud800'
json.dumps produces: {"value": "\ud800"}     ← and that JSON *is* utf-8 encodable
lone surrogate is NOT utf-8 encodable        ← so the write fails
```

So a client can put one in a request body, it passes validation, and it explodes at
the storage layer as an unhandled exception — a 500 with no useful message.
`atomic_write` now translates it into a `StorageError` naming the offending character
and its position. Two tests cover it, including one asserting that the previous file
contents survive and no temp file is left behind.

### A wrong comment of mine

A `\r`-only payload came back as `\n`, and my first instinct was that `newline="\n"`
was rewriting the content. I probed it instead of assuming, and the truth was the
opposite: the bytes on disk were `b'a\r\nb\rc\n'`, written faithfully, and it is
`read_text()` that applies *universal newlines* on the way back. The comment I had
written was wrong and the test asserted the wrong contract. Both are fixed, and line
endings now have byte-for-byte coverage.

### A test-harness issue

`DeadlineExceeded` on the first run: the first write to a fresh temp directory on
Windows can take several hundred milliseconds. These properties touch the disk and
timing is not what they assert, so `deadline=None` is set with the reason recorded.

---

## Review feedback applied

Six points raised after the first pass, all addressed:

**1. Cursor on the mode selector.** `cursor-pointer` on the unselected card only.
The active one keeps `cursor-default`, because a pointer implies "this does
something" and clicking the option you are already on does nothing.

**2. Model is a list, not free text.** `web/src/lib/models.ts` holds a curated
catalogue per provider — a typo in a model id would otherwise only surface as a
provider error mid-review, after tokens had been spent. Two escape hatches keep it
from becoming a cage: every provider allows a **Custom…** entry for a model released
after this build, and from phase 2 the OpenRouter list can be refreshed live from
`GET /api/v1/models`, demoting this file to an offline fallback. Changing provider
resets the model to that provider's recommendation, since ids are provider-specific.

**3. Fallback provider removed.** Design preserved in
[`DEFERRED-FALLBACK-PROVIDER.md`](DEFERRED-FALLBACK-PROVIDER.md), including the
failure taxonomy that makes it non-trivial: of seven failure classes, **only one**
actually justifies switching provider. Retrying a `401` elsewhere would hide a
misconfigured key indefinitely.

**4. Unlimited budgets.** `max_spend_usd` and `max_context_tokens` accept `null`,
modelled as `null` rather than a `0` or `-1` sentinel because those are
indistinguishable from a mistake — and a mistake in a spend cap is expensive. `0`
stays invalid. Selecting unlimited disables the input, shows "Unlimited" as its
placeholder, and raises a red danger panel quantifying the risk. The cross-field
validation is skipped when spending is unlimited, since there is no cap to exceed.

**5. English is the default.** The `pt-BR` you saw was residue from my own smoke
test writing to the real `~/.revai/config.yaml`, not a wrong default — the backend
has always defaulted to `en`. Two regression tests now pin it: one asserting the
default locale, one asserting a fresh install starts with **bounded** budgets so
unlimited can only ever be opt-in.

**6. Header navigates home.** The wordmark is a real `<Link>` — keyboard focus,
middle-click, and focus ring all come for free — and breadcrumb entries accept an
optional `href`. The current page is never a link.

### A migration this required

Removing the fallback fields would have **broken every existing `config.yaml`**,
because `extra="forbid"` rejects unknown keys and your file already contained
`fallback_provider_id`. I checked before editing rather than after. `EngineConfig`
now sets `extra="ignore"`, so an older file loads and the stale keys are dropped on
the next save. Two tests cover exactly that, and I verified it against the real file.

---

## Not in this phase

No providers, no git, no pipeline, no reviews.

**Next:** phase 2 — provider detection, health checks, the **OpenRouter adapter**,
and the **Detected providers** panel.
