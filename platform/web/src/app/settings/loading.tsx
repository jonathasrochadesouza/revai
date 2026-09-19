/**
 * Route loading state shared by the settings pages (Engine, Appearance, Data).
 * The active sub-page is unknown until the route resolves, so the frame stays
 * bare instead of guessing a breadcrumb trail.
 */

import { TopBar } from "@/components/top-bar";
import { LoadingPanel } from "@/components/ui/loader";

export default function Loading() {
  return (
    <>
      <TopBar />
      <LoadingPanel variant="snake" />
    </>
  );
}
