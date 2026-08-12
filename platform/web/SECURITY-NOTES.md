# Security notes

## Current status

```text
npm audit --omit=dev   →  0 vulnerabilities   ✅  (shipped code)
npm audit              →  2 high              ⚠️  (dev tooling only)
```

**Nothing that reaches a user's browser is affected.** Every open advisory sits in
the ESLint dependency tree, which runs only on a developer machine.

The runtime `nanoid` advisory was removed by pinning the patched 3.3.18 release
through the root override. The production audit is the release gate.

## The `brace-expansion` advisory (GHSA / ReDoS)

### What it is

A regular-expression denial of service in `brace-expansion`. A crafted glob pattern
can hang the process.

### Why it cannot currently be fixed

| Fact | Verified how |
|---|---|
| The advisory covers **`<=5.0.7`** — every published 1.x, 2.x, 3.x and 4.x release is in range | `npm audit --json` |
| The only patched release is **`5.0.8`** | `npm view brace-expansion@5 version` |
| The whole ESLint tree resolves **`minimatch@3.1.5`**, which requires `brace-expansion@^1.1.7` | `npm ls minimatch --all` |
| `brace-expansion@5` changed to a **named export**; `minimatch@3` calls it as a bare function | Reproduced locally — `TypeError` |
| The `maintenance-v1` line (`1.1.16`) is **not** patched | Reproduced the advisory PoC locally: OOM crash |
| `npm audit fix --force` "resolves" it by installing **`eslint@10`** | `fixAvailable` in the audit JSON |

Forcing `brace-expansion@5` breaks `eslint-plugin-react`, `eslint-plugin-import`,
`eslint-plugin-jsx-a11y`, `@eslint/eslintrc` and `@eslint/config-array` at once.
Upgrading to `eslint@10` breaks `eslint-config-next@16`, which is the config Next.js
ships and supports.

### Why the residual risk is acceptable

The vulnerability is only reachable by passing an attacker-controlled glob pattern
to the matcher. In this repository the only glob patterns are the ones written by
hand in `eslint.config.mjs`. There is no path from untrusted input to ESLint, and
ESLint is never part of a build artefact or runtime.

### Exit criteria

Recheck when either of these lands:

- `eslint-config-next` declares support for `eslint@10` — then upgrade and the whole
  chain resolves at the root, or
- the ESLint packages move to `minimatch@10`, which accepts `brace-expansion@^4`.

Until then, `npm run audit:prod` is the meaningful gate and it must stay at zero.

## Deliberate overrides

| Package | Pinned to | Reason |
|---|---|---|
| `nanoid` | `^3.3.17` | Pulls patched 3.3.18 for Next/PostCSS's runtime dependency |
| `postcss` | `^8.5.18` | Patches the transitive advisory without touching Tailwind |
| `sharp` | `^0.35.0` | Patched release; Next.js only uses it for image optimisation |

## Policy

- **`npm audit --omit=dev` must report zero.** This is enforced as the release gate.
- **Never run `npm audit fix --force` here.** It downgrades Next.js by six major
  versions, which is a far larger risk than any advisory it silences.
- Prefer a root-cause upgrade over an override. Document every override that remains.
