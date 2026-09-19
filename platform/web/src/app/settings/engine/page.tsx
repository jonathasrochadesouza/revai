/**
 * Settings › Engine.
 *
 * A server component fetches the configuration so the form renders already
 * populated — no loading spinner, no flash of empty inputs. The interactive part
 * lives in `settings-form.tsx`.
 */

import { BackendUnreachable } from "@/components/backend-unreachable";
import { SETTINGS_MENU, TopBar } from "@/components/top-bar";
import {
  api,
  API_BASE_URL,
  ApiError,
  type ConfigResponse,
  type CredentialsResponse,
} from "@/lib/api";

import { EnginePageHeader } from "./engine-unavailable";
import { AgentPanel } from "./agent-panel";
import { SettingsForm } from "./settings-form";

export const metadata = {
  title: "Engine · Settings — RevAI",
};

/** Either the loaded data or the reason it could not be loaded. */
type LoadResult =
  | { ok: true; config: ConfigResponse; credentials: CredentialsResponse }
  | { ok: false; reason: string };

/**
 * Fetch everything the page needs.
 *
 * Kept separate from rendering so no JSX is constructed inside a `try` — React
 * defers rendering, so a `catch` around JSX would never fire and would only give a
 * false sense of safety.
 */
async function load(): Promise<LoadResult> {
  try {
    // Requested together so a single round trip populates the whole form.
    const [config, credentials] = await Promise.all([
      api.getConfig(),
      api.getCredentials(),
    ]);
    return { ok: true, config, credentials };
  } catch (cause) {
    return { ok: false, reason: describe(cause) };
  }
}

export default async function EngineSettingsPage() {
  const result = await load();

  return (
    <>
      <TopBar
        breadcrumb={[{ label: "common.platform", href: "/" }, { label: "common.settings", menu: SETTINGS_MENU }, "common.engine"]}
      />
      <main className="mx-auto max-w-[820px] px-7 pb-20 pt-9">
        {result.ok ? (
          <>
            <EnginePageHeader configPath={result.config.path} />
            <SettingsForm
              initial={result.config}
              initialCredentials={result.credentials.credentials}
              credentialsPath={result.credentials.path}
            />
            <AgentPanel />
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
