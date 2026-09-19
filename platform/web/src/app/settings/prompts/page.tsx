/**
 * Settings › Prompts.
 *
 * Server component: fetches the prompt document so the form renders populated.
 * The interactive part lives in `prompts-form.tsx`.
 */

import { BackendUnreachable } from "@/components/backend-unreachable";
import { SETTINGS_MENU, TopBar } from "@/components/top-bar";
import {
  api,
  API_BASE_URL,
  ApiError,
  type ConfigResponse,
  type PromptsResponse,
} from "@/lib/api";

import { PromptsForm } from "./prompts-form";
import { PromptsPageHeader } from "./prompts-shell";

export const metadata = {
  title: "Prompts · Settings — RevAI",
};

type LoadResult =
  | { ok: true; prompts: PromptsResponse; config: ConfigResponse }
  | { ok: false; reason: string };

async function load(): Promise<LoadResult> {
  try {
    const [prompts, config] = await Promise.all([api.getPrompts(), api.getConfig()]);
    return { ok: true, prompts, config };
  } catch (cause) {
    return { ok: false, reason: describe(cause) };
  }
}

export default async function PromptsSettingsPage() {
  const result = await load();

  return (
    <>
      <TopBar
        breadcrumb={[
          { label: "common.platform", href: "/" },
          { label: "common.settings", menu: SETTINGS_MENU },
          "common.prompts",
        ]}
      />
      <main className="mx-auto max-w-[820px] px-7 pb-20 pt-9">
        {result.ok ? (
          <>
            <PromptsPageHeader path={result.prompts.path} locale={result.prompts.locale} />
            <PromptsForm initial={result.prompts} config={result.config.config} />
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
