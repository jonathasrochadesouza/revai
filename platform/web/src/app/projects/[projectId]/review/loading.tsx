/**
 * Route loading state for the review screen. The project name is resolved by
 * the page itself, so the frame falls back to the generic "Review" trail.
 */

import { TopBar } from "@/components/top-bar";
import { LoadingPanel } from "@/components/ui/loader";

export default function Loading() {
  return (
    <>
      <TopBar breadcrumb={[{ label: "Projects", href: "/" }, "Review"]} />
      <LoadingPanel variant="skeleton" />
    </>
  );
}
