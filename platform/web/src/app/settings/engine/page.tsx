/**
 * Settings › Engine.
 *
 * A server component fetches the configuration so the form renders already
 * populated — no loading spinner, no flash of empty inputs. The interactive part
 * lives in `settings-form.tsx`.
 */

import Link from "next/link";

import { TopBar } from "@/components/top-bar";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import {
  api,
  API_BASE_URL,
  ApiError,
  type ConfigResponse,
  type CredentialsResponse,
} from "@/lib/api";

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
        breadcrumb={[{ label: "Platform", href: "/" }, "Settings", "Engine"]}
      />
      <main className="mx-auto max-w-[820px] px-7 pb-20 pt-9">
        {result.ok ? (
          <>
            <div className="mb-7">
              <p className="eyebrow mb-2">Settings</p>
              <h1 className="mb-2.5 text-[26px] font-bold tracking-[-0.7px]">
                Engine &amp; providers
              </h1>
              <p className="max-w-[70ch] text-[14px] leading-relaxed text-ink-muted">
                Choose how RevAI reaches a model. Everything is written to{" "}
                <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[12.5px] text-low">
                  {result.config.path}
                </code>{" "}
                — plain text you can read, diff and version.
              </p>
            </div>

            <SettingsForm
              initial={result.config}
              initialCredentials={result.credentials.credentials}
              credentialsPath={result.credentials.path}
            />
          </>
        ) : (
          <Unreachable reason={result.reason} />
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

/**
 * Shown when the backend is unreachable or its config file is malformed.
 *
 * The distinction matters: a 422 means the YAML is broken and the message names the
 * field, whereas a network failure means the process is not running.
 */
function Unreachable({ reason }: { reason: string }) {
  return (
    <>
      <div className="mb-7">
        <p className="eyebrow mb-2">Settings</p>
        <h1 className="text-[26px] font-bold tracking-[-0.7px]">Engine &amp; providers</h1>
      </div>

      <Card>
        <CardHeader title="Configuration unavailable" icon={ALERT} aside={API_BASE_URL} />
        <CardBody>
          <div className="rounded-control border border-critical-line bg-critical-surface p-4">
            <p className="mb-2 text-[13.5px] font-semibold text-critical">
              The API did not return a configuration
            </p>
            <p className="mb-3 text-[12.5px] leading-relaxed text-ink-muted">{reason}</p>
            <p className="mb-2 text-[12.5px] text-ink-muted">
              If the backend is not running, start it in a second terminal:
            </p>
            <pre className="overflow-x-auto rounded-chip border border-line bg-paper px-3 py-2.5 text-[11.5px] leading-relaxed">
              {"cd platform/api\nuv sync --all-groups\nuv run revai-api"}
            </pre>
          </div>

          <p className="mt-4 text-[12.5px] text-ink-muted">
            <Link href="/" className="text-low hover:underline">
              ← Back to the dashboard
            </Link>
          </p>
        </CardBody>
      </Card>
    </>
  );
}

const ALERT = (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    className="size-[15px] text-critical"
  >
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
  </svg>
);
