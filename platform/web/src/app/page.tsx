import { ProjectWorkspace } from "@/components/projects/project-workspace";
import { TopBar } from "@/components/top-bar";
import { api, type Project } from "@/lib/api";

async function loadProjects(): Promise<{
  projects: Project[];
  connected: boolean;
  reason?: string;
}> {
  try {
    const response = await api.getProjects();
    return { projects: response.projects, connected: true };
  } catch (error) {
    return {
      projects: [],
      connected: false,
      reason: error instanceof Error ? error.message : "Could not reach the API.",
    };
  }
}

export default async function Home() {
  const state = await loadProjects();
  const renderedAt = new Date().toISOString();

  return (
    <>
      {/* No connection chip here: the global banner covers the failure case on every
          screen, and the detail lives on Settings › API & AI. The load failure is
          still reported by the workspace itself. */}
      <TopBar breadcrumb={["common.platform", "common.projects"]} />
      <ProjectWorkspace
        initialProjects={state.projects}
        initialError={state.reason}
        renderedAt={renderedAt}
      />
    </>
  );
}
