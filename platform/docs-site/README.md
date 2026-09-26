# RevAI documentation site

Built with [Docusaurus](https://docusaurus.io/). Source content lives under
`docs/` (English, the default locale) and `i18n/pt-BR/docusaurus-plugin-content-docs/current/`
(Brazilian Portuguese).

## Development

```bash
npm install
npm start              # English at http://localhost:3000
npm run start:pt-BR    # Portuguese at http://localhost:3000/pt-BR
```

## Build

```bash
npm run build           # outputs both locales into build/
npm run serve            # preview the production build locally
```

## Adding a page

1. Create the `.md` file under the right category directory in `docs/`
   (`start-here/`, `reviewing/`, or `advanced/`), with front matter
   (`id`, `title`, `sidebar_position`).
2. Add its `id` to `sidebars.ts`.
3. Create the pt-BR translation at the mirrored path under
   `i18n/pt-BR/docusaurus-plugin-content-docs/current/`.
4. Run `npm run write-translations -- --locale pt-BR` if you added new
   navbar/footer/theme strings, then fill in the generated JSON.

## Structure

```
docs/
├── index.md                    overview page (slug: /)
├── start-here/                  getting-started, run-the-backend
├── reviewing/                    providers, first-review, findings-and-fix
└── advanced/                     cli-and-ci, privacy-and-data
```

Shell commands, file paths and product names are never translated — they
are identical in every locale and are written directly into the Markdown
body rather than through the i18n layer, mirroring the convention used by
the rest of the RevAI codebase.
