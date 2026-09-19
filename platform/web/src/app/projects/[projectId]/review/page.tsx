import { AllProjectsLink, BackToProjectsLink } from "@/components/links";
import { ReviewPageHeader, UnavailableNotice } from "@/components/page-header";
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
            { label: "common.projects", href: "/" },
            project.name,
            "review.reviewSetup",
          ]}
        />
        <main className="mx-auto w-full max-w-[1280px] px-5 pb-20 pt-9 sm:px-7">
          <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
            <ReviewPageHeader />
            <AllProjectsLink />
          </div>
          <ReviewSetupWorkspace project={project} />
        </main>
      </>
    );
  }

  return (
    <>
      <TopBar breadcrumb={[{ label: "common.projects", href: "/" }, "review.eyebrow"]} />
      <main className="mx-auto w-full max-w-[820px] px-5 pb-20 pt-9 sm:px-7">
        <div className="surface border-critical-line bg-critical-surface p-5">
          <UnavailableNotice variant="review" reason={error ?? ""} />
          <BackToProjectsLink />
        </div>
      </main>
    </>
  );
}
