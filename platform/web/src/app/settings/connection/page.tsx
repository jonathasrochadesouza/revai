/**
 * Settings › API & AI.
 *
 * No server fetch: the status lives in the layout-level connection store, which has
 * usually already answered by the time this route renders, and the screen must work
 * when the backend is down — the exact case a server fetch cannot render.
 */

import { SettingsPageHeader } from "@/components/page-header";
import { SETTINGS_MENU, TopBar } from "@/components/top-bar";

import { ConnectionPanels } from "./connection-panels";

export const metadata = {
  title: "API & AI · Settings — RevAI",
};

export default function ConnectionSettingsPage() {
  return (
    <>
      <TopBar
        breadcrumb={[
          { label: "common.platform", href: "/" },
          { label: "common.settings", menu: SETTINGS_MENU },
          "common.apiAndAi",
        ]}
      />
      <main className="mx-auto w-full max-w-[820px] px-5 pb-20 pt-9 sm:px-7">
        <SettingsPageHeader page="connection" />
        <ConnectionPanels />
      </main>
    </>
  );
}
