import { ExportDataPanel, type ReviewExportRow } from "@/components/data/export-data-panel";
import { EngineLink } from "@/components/links";
import { SettingsPageHeader, UnavailableNotice } from "@/components/page-header";
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
      <TopBar breadcrumb={[{ label: "common.platform", href: "/" }, { label: "common.settings", menu: SETTINGS_MENU }, "common.data"]}>
        <EngineLink />
      </TopBar>
      <main className="mx-auto w-full max-w-[900px] px-5 pb-20 pt-9 sm:px-7">
        <SettingsPageHeader page="data" />
        {result.ok ? <ExportDataPanel summary={result.summary} reviews={result.reviews} /> : <UnavailableNotice variant="data" reason={result.reason} />}
      </main>
    </>
  );
}
