import Link from "next/link";

import { ExportDataPanel, type ReviewExportRow } from "@/components/data/export-data-panel";
import { SETTINGS_MENU, TopBar } from "@/components/top-bar";
import { api, type DataSummary } from "@/lib/api";

export const metadata = {
  title: "Export & data · Settings — RevAI",
};

type LoadResult =
  | { ok: true; summary: DataSummary; reviews: ReviewExportRow[] }
  | { ok: false; reason: string };

async function load(): Promise<LoadResult> {
  try {
    const summaryPromise = api.getDataSummary();
    const projects = await api.getProjects();
    const reviewResponses = await Promise.all(
      projects.projects.map((project) => api.getProjectReviews(project.id)),
    );
    const projectNames = new Map(projects.projects.map((project) => [project.id, project.name]));
    const reviews = reviewResponses
      .flatMap((response) => response.reviews)
      .toSorted((left, right) => right.created_at.localeCompare(left.created_at))
      .slice(0, 12)
      .map((review) => ({ projectName: projectNames.get(review.project_id) ?? "Unknown project", review }));
    return { ok: true, summary: await summaryPromise, reviews };
  } catch (cause) {
    return { ok: false, reason: cause instanceof Error ? cause.message : "Could not reach the API." };
  }
}

export default async function DataSettingsPage() {
  const result = await load();
  return (
    <>
      <TopBar breadcrumb={[{ label: "Platform", href: "/" }, { label: "Settings", menu: SETTINGS_MENU }, "Data"]}>
        <Link href="/settings/engine" className="rounded-control border border-line-strong px-3 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink">Engine</Link>
      </TopBar>
      <main className="mx-auto w-full max-w-[900px] px-5 pb-20 pt-9 sm:px-7">
        <div className="mb-7">
          <p className="eyebrow mb-2">Settings</p>
          <h1 className="mb-2.5 text-[26px] font-bold tracking-[-0.7px]">Export &amp; data</h1>
          <p className="max-w-[70ch] text-[14px] leading-relaxed text-ink-muted">Download individual reports or a complete portable archive. Exports are generated locally from YAML and never include API credentials.</p>
        </div>
        {result.ok ? <ExportDataPanel summary={result.summary} reviews={result.reviews} /> : <div className="surface border-critical-line bg-critical-surface px-5 py-5"><h2 className="text-[13px] font-semibold text-critical">Data unavailable</h2><p className="mt-2 text-[12px] text-ink-muted">{result.reason}</p></div>}
      </main>
    </>
  );
}
