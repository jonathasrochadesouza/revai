import Link from "next/link";

import { ReviewSetupWorkspace } from "@/components/projects/project-workspace";
import { TopBar } from "@/components/top-bar";
import { api, ApiError } from "@/lib/api";

export const metadata = {
  title: "Review setup — RevAI",
};

async function loadProject(projectId: string) {
  try {
    return { project: await api.getProject(projectId), error: null };
  } catch (cause) {
    return {
      project: null,
      error:
        cause instanceof ApiError || cause instanceof Error
          ? cause.message
          : "Could not load this project.",
    };
  }
}

export default async function ReviewSetupPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { project, error } = await loadProject(projectId);

  if (project) {
    return (
      <>
        <TopBar
          breadcrumb={[
            { label: "Projects", href: "/" },
            project.name,
            "Review setup",
          ]}
        />
        <main className="mx-auto w-full max-w-[1280px] px-5 pb-20 pt-9 sm:px-7">
          <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="eyebrow mb-2">Review</p>
              <h1 className="mb-2 text-[26px] font-bold tracking-[-0.7px]">
                Configure a review
              </h1>
              <p className="max-w-[68ch] text-[14px] leading-relaxed text-ink-muted">
                Choose the branch comparison, inspect the proposed context and run
                the review when the scope and estimated cost look right.
              </p>
            </div>
            <Link
              href="/"
              className="rounded-control border border-line-strong px-3 py-2 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink"
            >
              ← All projects
            </Link>
          </div>
          <ReviewSetupWorkspace project={project} />
        </main>
      </>
    );
  }

  return (
    <>
      <TopBar breadcrumb={[{ label: "Projects", href: "/" }, "Review"]} />
      <main className="mx-auto w-full max-w-[820px] px-5 pb-20 pt-9 sm:px-7">
        <div className="surface border-critical-line bg-critical-surface p-5">
          <h1 className="text-[15px] font-semibold text-critical">Project unavailable</h1>
          <p className="mt-2 text-[13px] text-ink-muted">{error}</p>
          <Link
            href="/"
            className="mt-4 inline-block text-[12px] font-medium text-low hover:underline"
          >
            Back to projects
          </Link>
        </div>
      </main>
    </>
  );
}
