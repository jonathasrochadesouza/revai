/**
 * Route loading state for the dashboard. Shown while the server component
 * fetches the project list; the top bar frame stays visible.
 */

import { TopBar } from "@/components/top-bar";
import { LoadingPanel } from "@/components/ui/loader";

export default function Loading() {
  return (
    <>
      <TopBar />
      <LoadingPanel variant="spinner" />
    </>
  );
}
