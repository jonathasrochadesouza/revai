/**
 * Settings › Skills & Prompts.
 *
 * Server component: fetches the prompt document and the installed skills so
 * both tabs render populated. The interactive part lives in
 * `skills-prompts-tabs.tsx` (tabs) → `skills-tab.tsx` (marketplace) and
 * `prompts-form.tsx` (prompts + scenarios).
 */

import { BackendUnreachable } from "@/components/backend-unreachable";
import { SETTINGS_MENU, TopBar } from "@/components/top-bar";
import {
  api,
  API_BASE_URL,
  ApiError,
  type ConfigResponse,
  type InstalledSkillsResponse,
  type PromptsResponse,
} from "@/lib/api";

import { SkillsPromptsTabs } from "./skills-prompts-tabs";
import { SkillsPageHeader } from "./skills-shell";

export const metadata = {
  title: "Skills & Prompts · Settings — RevAI",
};

type LoadResult =
  | {
      ok: true;
      prompts: PromptsResponse;
      config: ConfigResponse;
      skills: InstalledSkillsResponse;
    }
  | { ok: false; reason: string };

async function load(): Promise<LoadResult> {
  try {
    const [prompts, config, skills] = await Promise.all([
      api.getPrompts(),
      api.getConfig(),
      api.getInstalledSkills(),
    ]);
    return { ok: true, prompts, config, skills };
  } catch (cause) {
    return { ok: false, reason: describe(cause) };
  }
}

export default async function SkillsSettingsPage() {
  const result = await load();

  return (
    <>
      <TopBar
        breadcrumb={[
          { label: "common.platform", href: "/" },
          { label: "common.settings", menu: SETTINGS_MENU },
          "common.skillsPrompts",
        ]}
      />
      <main className="mx-auto max-w-[820px] px-7 pb-20 pt-9">
        {result.ok ? (
          <>
            <SkillsPageHeader
              skillsPath={result.skills.path}
              promptsPath={result.prompts.path}
              locale={result.prompts.locale}
            />
            <SkillsPromptsTabs
              initial={result.prompts}
              config={result.config.config}
              skills={result.skills.skills}
            />
          </>
        ) : (
          <BackendUnreachable reason={result.reason} apiBaseUrl={API_BASE_URL} />
        )}
      </main>
    </>
  );
}

function describe(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  if (cause instanceof Error) return cause.message;
  return "Unknown error";
}
