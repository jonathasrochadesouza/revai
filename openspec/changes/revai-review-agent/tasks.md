## 1. Template and renderer

- [x] 1.1 Add the packaged `revai/templates/agent-report.html` (Paper Light
      CSS, hero/metrics/meta/filter/findings sections, fixed vanilla renderer)
      with exactly one `__REVAI_DATA__` placeholder inside a
      `<script type="application/json" id="revai-data">` node, and a
      `revai/templates/__init__.py` so `importlib.resources` can load it.
- [x] 1.2 Add `revai/agents/renderer.py`: `load_template`, `inject_data`
      (exactly-one-placeholder contract, `</` escaping), `validate_payload`
      (strict `_FindingEnvelope` first, compact fallback), `slugify_name`,
      `report_filename`, and `render_report` (never writes an invalid
      payload).
- [x] 1.3 Renderer tests: placeholder uniqueness, script-tag escaping, both
      payload shapes, garbage rejection, output filename, error rendering.

## 2. Generator and installer

- [x] 2.1 Add `revai/agents/generator.py`: managed block
      (`revai:begin`/`revai:end`) carrying the locale-aware persona, the
      prompt-injection guard, the compact findings contract, the render
      workflow, the read-only permission section, and project rules from
      `~/.revai/rules/*.md`; `compose_document` is idempotent.
- [x] 2.2 Add `revai/agents/installer.py`: writes `AGENTS.md` (merge or
      replace, one-time `.revai-bak` backup) and `.revai/agent-report.html`;
      `dry_run` writes nothing; non-directory targets raise.
- [x] 2.3 Generator/installer tests: markers, persona and guard presence, no
      secrets in the block, rules inlining, idempotency, merge preservation,
      backup behavior, dry run.

## 3. CLI

- [x] 3.1 Add `revai agent install [path] [--provider --model --locale
      --dry-run --yes]` (interactive confirm; piped stdin requires `--yes`)
      and `revai agent render <json> --name <slug> [--out --template
      --dry-run]` following the existing `cli.py` dispatch pattern.
- [x] 3.2 CLI tests: dry run prints without writing, `--yes` writes both
      files, piped input without confirmation refuses, render writes
      `<slug>-revai.html`, invalid payload exits 2.

## 4. API and web UI

- [x] 4.1 Add `api/routes/agent.py`: `GET /api/agent/preview` (merged
      document + paths), `POST /api/agent/apply` (writes after explicit
      call), `GET /api/agent/report-demo` (rendered sample report); register
      the router in `main.py`; structured errors (`agent.*` keys) for unknown
      projects, missing paths, and write failures.
- [x] 4.2 Add Settings › Engine → "Review agent (AGENTS.md)" panel
      (`agent-panel.tsx`): project picker, preview of the merged AGENTS.md,
      install button with result feedback, and a toggleable iframe of the
      sample report; wire client methods in `lib/api.ts` and `agent.*` i18n
      keys in both catalogs (parity test updated).
- [x] 4.3 Route tests: preview (existing/new file), apply writes both files,
      unknown project 404, sample report renders.

## 5. Verification

- [x] 5.1 `ruff check`/`format` clean on all touched backend files.
- [x] 5.2 Backend suite green (`pytest`: 337 passed), frontend `tsc`, `eslint`
      and `vitest` green.
- [x] 5.3 Manual smoke: `revai agent install` + `revai agent render` against a
      scratch project produce `AGENTS.md`, `.revai/agent-report.html`, and a
      `<slug>-revai.html` whose placeholder is replaced.
- [ ] 5.4 Verify the sample report in a browser (filters, patch details,
      empty state) and in dark theme.
