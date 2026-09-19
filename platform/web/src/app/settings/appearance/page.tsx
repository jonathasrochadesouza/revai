import Link from "next/link";

import { SETTINGS_MENU, TopBar } from "@/components/top-bar";
import { api, ApiError, type ConfigResponse } from "@/lib/api";

import { AppearanceForm } from "./appearance-form";

export const metadata = { title: "Appearance · Settings — RevAI" };

export default async function AppearanceSettingsPage() {
  let config: ConfigResponse | null = null;
  let reason: string | null = null;
  try {
    config = await api.getConfig();
  } catch (cause) {
    reason = cause instanceof ApiError || cause instanceof Error ? cause.message : "Could not reach the API.";
  }

  return (
    <>
      <TopBar breadcrumb={[{ label: "Platform", href: "/" }, { label: "Settings", menu: SETTINGS_MENU }, "Appearance"]}>
        <Link href="/settings/engine" className="rounded-control border border-line-strong px-3 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink">Engine</Link>
      </TopBar>
      <main className="mx-auto w-full max-w-[820px] px-5 pb-20 pt-9 sm:px-7">
        <div className="mb-7">
          <p className="eyebrow mb-2">Settings</p>
          <h1 className="mb-2.5 text-[26px] font-bold tracking-[-0.7px]">Appearance &amp; language</h1>
          <p className="max-w-[70ch] text-[14px] leading-relaxed text-ink-muted">Set a comfortable workspace and the locale RevAI uses for its interface. These preferences stay on your machine in config.yaml.</p>
        </div>
        {config ? <AppearanceForm initial={config} /> : <section className="surface border-critical-line bg-critical-surface px-5 py-5"><h2 className="text-[13px] font-semibold text-critical">Preferences unavailable</h2><p className="mt-2 text-[12px] text-ink-muted">{reason}</p></section>}
      </main>
    </>
  );
}
