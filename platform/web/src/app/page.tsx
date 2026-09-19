import { ApiStatusBadge } from "@/components/api-status-badge";
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
      <TopBar breadcrumb={["common.platform", "common.projects"]}>
        <ApiStatusBadge connected={state.connected} />
      </TopBar>
      <ProjectWorkspace
        initialProjects={state.projects}
        initialError={state.reason}
        renderedAt={renderedAt}
      />
    </>
  );
}
