/**
 * Route loading state for the Insights screen. The breadcrumb is static, so
 * the frame can render with the full trail while data loads.
 */

import { TopBar } from "@/components/top-bar";
import { LoadingPanel } from "@/components/ui/loader";

export default function Loading() {
  return (
    <>
      <TopBar breadcrumb={[{ label: "Platform", href: "/" }, "Insights"]} />
      <LoadingPanel />
    </>
  );
}
