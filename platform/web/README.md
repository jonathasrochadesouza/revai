# RevAI Web

Next.js frontend for the RevAI Platform, built on the **Paper Light** design system.

## Requirements

- Node.js 20+
- The [API](../api/README.md) running on `http://127.0.0.1:8799`

## Getting started

```bash
npm install
npm run dev        # http://localhost:3000
```

The page renders even when the backend is down — that is exactly when you need to be
told how to start it.

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Development server on port 3000 |
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm run typecheck` | `tsc --noEmit` |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8799` | Backend base URL |

## Design system

Defined entirely in `src/app/globals.css` as Tailwind v4 `@theme` tokens, ported from
`../mocks/03-review-config.html`.

| Token group | Names |
|---|---|
| Surfaces | `canvas` · `paper` · `sunken` |
| Ink | `ink` · `ink-muted` · `ink-subtle` |
| Lines | `line` · `line-strong` |
| Severity | `critical` · `medium` · `low` (+ `-surface`, `-line`) |
| State | `info` · `success` |

Four rules, in order of importance:

1. **Colour carries meaning, never decoration.** Emphasis comes from contrast — the
   primary button is near-black, not blue.
2. **Hairline 1px borders.** No gradients, no blur, no coloured shadows.
3. **Generous whitespace.**
4. **Numbers, paths and code are always monospaced** and tabular.

Dark mode ships later by remapping the same token names — no component changes.

## Layout

```
src/
├── app/
│   ├── globals.css      the design system
│   ├── layout.tsx       fonts + metadata
│   ├── insights/        aggregate code-health dashboard
│   ├── settings/data/   review and portable data exports
│   └── page.tsx         projects workspace
├── components/
│   ├── projects/        repository entry, list, tree and diff inspector
│   ├── ui/              badge · card
│   ├── logo.tsx
│   └── top-bar.tsx
└── lib/
    └── api.ts           typed API client
```

Current phase: **8 — CLI adapters**. Settings › Engine exposes Claude Code, GitHub
Copilot CLI, and Kiro CLI as implemented local engines while preserving their real
installed, sign-in, unknown, timeout, and error states. See
[`../docs/PHASE-8.md`](../docs/PHASE-8.md).
