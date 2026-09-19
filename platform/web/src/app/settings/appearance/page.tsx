import { EngineLink } from "@/components/links";
import { SettingsPageHeader, UnavailableNotice } from "@/components/page-header";
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
      <TopBar breadcrumb={[{ label: "common.platform", href: "/" }, { label: "common.settings", menu: SETTINGS_MENU }, "common.appearance"]}>
        <EngineLink />
      </TopBar>
      <main className="mx-auto w-full max-w-[820px] px-5 pb-20 pt-9 sm:px-7">
        <SettingsPageHeader page="appearance" />
        {config ? <AppearanceForm initial={config} /> : <UnavailableNotice variant="appearance" reason={reason ?? ""} />}
      </main>
    </>
  );
}
