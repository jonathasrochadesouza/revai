# Changelog

All notable changes to RevAI are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Settings › Prompts**: the two AI review prompts (system + user) become
  first-class configuration. Built-in defaults ship translated for en-US and
  pt-BR; customisations are stored per locale; "restore built-in" works per
  field and globally.
- **Prompt scenarios** (e.g. "Backend - Java"): independent snapshots of both
  prompts, created from the effective defaults, editable and deletable, and
  selectable per review (review panel dropdown, API `scenario_id`, CLI
  `--scenario`). Retry reuses the original scenario.
- **Friendly error messages (frontend)**: every API error resolves through a
  translated `error_key` catalog (`lib/errors.ts`) instead of surfacing raw
  keys; a shared toast system replaces per-screen error banners; settings
  pages render a real backend-unreachable recovery screen with a copyable AI
  troubleshooting prompt.
- **Document migrations**: persisted YAML documents upgrade automatically via
  `revai/storage/migrations.py`; files from unknown or future schema versions
  fail with a structured error instead of being half-interpreted.
- **Coverage tooling**: `pytest --cov` (gate at 75% in CI) and
  `npm run test:coverage` (gate on the error catalog).
- **Community docs**: `CONTRIBUTING.md`, `SECURITY.md`, root `.gitignore`.
- **Release automation**: tag-driven `release` workflow (GitHub Release with
  wheel/sdist + PyPI trusted publishing) and this changelog.

### Changed
- The API version now comes from a single source of truth
  (`revai/__version__`, read by hatchling at build time).
- `ApiError` in the web client carries `errorKey`/`params`; `message` is a
  locale-agnostic fallback. The SSE `failed` event type matches the backend
  contract (`error_key` + `params`).

### Fixed
- pt-BR catalog: "Contêiner" spelling; the settings prompts save bar no
  longer pins mid-page (sticky placement now matches the Engine screen).

## [3.0.0a0] — 2026-07-28

Alpha establishing the full hybrid pipeline: deterministic analyzers
(security, semgrep, ruff, eslint, gitleaks, checkstyle, tree-sitter,
SonarQube), structured AI streaming across hosted APIs and CLI agents, budget
guards with hard stops, YAML persistence under `~/.revai/`, projects +
review history, insights, exports (JSON/MD/HTML/SARIF), one-screen local
SonarQube provisioning over Docker, hardened containers, and full pt-BR
localization.
