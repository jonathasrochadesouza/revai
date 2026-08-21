import { ProjectWorkspace } from "@/components/projects/project-workspace";
import { TopBar } from "@/components/top-bar";
import { Badge } from "@/components/ui/badge";
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
      <TopBar breadcrumb={["Platform", "Projects"]}>
        <span className="hidden sm:inline-flex">
          <Badge tone={state.connected ? "success" : "critical"} dot>
            {state.connected ? "API connected" : "API unreachable"}
          </Badge>
        </span>
      </TopBar>
      <ProjectWorkspace
        initialProjects={state.projects}
        initialError={state.reason}
        renderedAt={renderedAt}
      />
    </>
  );
}
