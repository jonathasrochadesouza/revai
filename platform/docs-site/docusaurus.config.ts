import type * as Preset from "@docusaurus/preset-classic";
import type { Config } from "@docusaurus/types";
import { themes as prismThemes } from "prism-react-renderer";

const config: Config = {
  title: "RevAI",
  tagline: "Local-first AI code review for Git repositories",
  favicon: "img/logo.svg",

  future: {
    v4: true,
  },

  url: "https://docs.revai.dev",
  baseUrl: "/",

  organizationName: "revai",
  projectName: "revai-docs",

  onBrokenLinks: "throw",
  onBrokenAnchors: "warn",

  markdown: {
    hooks: {
      onBrokenMarkdownLinks: "warn",
    },
  },

  i18n: {
    defaultLocale: "en-US",
    locales: ["en-US", "pt-BR"],
    localeConfigs: {
      "en-US": { label: "English", htmlLang: "en-US" },
      "pt-BR": { label: "Português (Brasil)", htmlLang: "pt-BR" },
    },
  },

  presets: [
    [
      "classic",
      {
        docs: {
          routeBasePath: "/",
          sidebarPath: "./sidebars.ts",
          editUrl: undefined,
          breadcrumbs: true,
        },
        blog: false,
        theme: {
          customCss: "./src/css/custom.css",
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      defaultMode: "light",
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: "RevAI",
      logo: {
        alt: "RevAI logo",
        src: "img/logo.svg",
      },
      items: [
        {
          type: "docSidebar",
          sidebarId: "docs",
          position: "left",
          label: "Docs",
        },
        {
          href: "https://github.com/jonathasrochadesouza/revai",
          label: "GitHub",
          position: "right",
        },
        {
          type: "localeDropdown",
          position: "right",
        },
      ],
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Docs",
          items: [
            { label: "Getting started", to: "/getting-started" },
            { label: "Running a review", to: "/first-review" },
            { label: "CLI and CI", to: "/cli-and-ci" },
          ],
        },
        {
          title: "More",
          items: [
            { label: "GitHub", href: "https://github.com/jonathasrochadesouza/revai" },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} RevAI.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ["bash", "yaml", "json"],
    },
    docs: {
      sidebar: {
        hideable: true,
        autoCollapseCategories: true,
      },
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
