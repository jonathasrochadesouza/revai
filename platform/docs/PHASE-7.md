# Phase 7 — Export & Insights

Implemented and verified on **2026-08-02**.

Phase 7 makes persisted review data useful outside the live review screen. Every
report and dashboard metric is generated locally from the existing YAML stores;
exports never include API credentials, caches, or repository contents.

## Delivered

- Export one review as versioned JSON, pull-request-ready Markdown, or a
  self-contained offline HTML report.
- Export the legacy finding JSON shape consumed by the original PowerShell report
  and import it back into the current domain model.
- Escape dynamic Markdown and HTML values; standalone HTML contains no scripts,
  remote assets, or network dependencies.
- Build a portable ZIP containing the current configuration, custom rules,
  projects, and reviews as JSON.
- Exclude `credentials.yaml`, caches, Git repositories, symlink targets, and source
  content from the archive.
- Aggregate review counts, finding categories and statuses, spend, duration,
  twelve-review trends, and per-repository health.
- Filter insights over 7, 30, or 90 days, or the complete history.
- Render responsive Paper Light Insights and Settings › Data pages.
- Isolate Tree-sitter parsing in a bounded helper process after live mixed-language
  validation exposed a native grammar crash.

## HTTP API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/reviews/{review_id}/export?format=json` | Versioned review JSON |
| `GET` | `/api/reviews/{review_id}/export?format=md` | Markdown report |
| `GET` | `/api/reviews/{review_id}/export?format=html` | Standalone HTML report |
| `GET` | `/api/reviews/{review_id}/export?format=json&legacy=true` | Legacy finding array |
| `GET` | `/api/insights?range=30d` | Dashboard metrics (`7d`, `30d`, `90d`, `all`) |
| `GET` | `/api/data` | Local storage summary |
| `POST` | `/api/export/all` | Portable ZIP archive |

The modern JSON envelope carries `format_version: 1`, `exported_at`, project
metadata, and the complete persisted review. Legacy export is intentionally
lossier and contains only `title`, `priority`, `description`, `copilotSummary`,
`file`, and `lines`.

## Insight Semantics

Totals and trend points include reviews created in the selected period. The trend
contains the latest twelve reviews in chronological order. Repository health uses
the most recent review in that period and subtracts 15 points per open critical
finding, 5 per open medium finding, and 1 per open low finding, with a floor of 0.
The change is measured against that repository's preceding review.

## Verification

The test suite covers every format, legacy round-trip compatibility, HTML and
Markdown escaping, invalid requests, missing reviews, time-range aggregation,
archive contents, and credential exclusion. A regression test also parses
TypeScript and Python in one review so native parser failures cannot crash the API.

Live validation used a temporary data directory and this repository as the project:

- a deterministic HTTP review completed across 637 source chunks;
- Insights rendered at desktop and mobile widths with no horizontal page overflow;
- the 7-day period interaction refreshed successfully;
- JSON and ZIP downloads returned valid payloads;
- `unzip -t` verified every archive member;
- Chromium reported no console errors or framework error overlay.

Run the complete verification gate with:

```bash
cd platform/api
uv run pytest
uv run ruff check revai tests

cd ../web
npm run typecheck
npm run lint
npm run build
npm run audit:prod
```
