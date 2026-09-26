import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectWorkspace } from "@/components/projects/project-workspace";
import type { Project } from "@/lib/api";

vi.mock("@/components/toast-provider", () => ({
  useToast: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getConfig: vi.fn().mockResolvedValue({
        config: {
          schema_version: 6,
          engine: { mode: "api", provider_id: "openrouter", model: "anthropic/claude-sonnet-5", base_url: null },
          budget: { max_spend_usd: 0.5, max_context_tokens: 60000, warn_above_usd: 0.25, request_timeout_s: 600, max_concurrent_reviews: 1, max_retry_attempts: 1 },
          analyzers: {},
          ui: { locale: "en-US", theme: "system", confirm_expensive_reviews: true, auto_save: null, hide_getting_started_checklist: true },
          updated_at: new Date().toISOString(),
        },
        path: "~/.revai/config.yaml",
        exists: true,
      }),
      verifyProvider: vi.fn().mockResolvedValue({
        provider_id: "openrouter",
        kind: "api",
        state: "ready",
        version: null,
        executable: null,
        detail: null,
        remediation: null,
        adapter_ready: true,
        checked_at: new Date().toISOString(),
      }),
      getProjects: vi.fn().mockResolvedValue({ projects: [] }),
      createCloudProject: vi.fn(),
    },
  };
});

import { api } from "@/lib/api";

function cloudProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "p1",
    name: "acme/widgets",
    kind: "cloud",
    path: null,
    remote_url: "https://github.com/acme/widgets.git",
    base_branch: "main",
    current_branch: null,
    branches: [],
    languages: ["TypeScript"],
    checkstyle_command: [],
    test_command: [],
    build_command: [],
    archived: false,
    created_at: new Date().toISOString(),
    last_reviewed_at: null,
    ...overrides,
  };
}

function localProject(overrides: Partial<Project> = {}): Project {
  return {
    ...cloudProject(overrides),
    kind: "local_open",
    path: "C:\\Dev\\widgets",
    remote_url: null,
    ...overrides,
  };
}

describe("ProjectWorkspace", () => {
  afterEach(cleanup);

  it("offers a third entry point to review a remote repository without cloning", () => {
    render(<ProjectWorkspace initialProjects={[]} renderedAt={new Date().toISOString()} />);

    expect(
      screen.getByRole("button", { name: /review a remote repository/i }),
    ).not.toBeNull();
  });

  it("shows a cloud badge next to cloud projects but not local ones", () => {
    render(
      <ProjectWorkspace
        initialProjects={[cloudProject(), localProject({ id: "p2", name: "local/repo" })]}
        renderedAt={new Date().toISOString()}
      />,
    );

    const rows = screen.getAllByRole("link");
    const cloudRow = rows.find((row) => row.textContent?.includes("acme/widgets"));
    const localRow = rows.find((row) => row.textContent?.includes("local/repo"));

    expect(cloudRow?.textContent).toContain("Cloud");
    expect(localRow?.textContent).not.toContain("Cloud");
  });

  it("opens the cloud creation dialog with a URL field and an optional base branch field", async () => {
    const user = userEvent.setup();
    render(<ProjectWorkspace initialProjects={[]} renderedAt={new Date().toISOString()} />);

    await user.click(screen.getByRole("button", { name: /review a remote repository/i }));

    expect(screen.getByRole("dialog")).not.toBeNull();
    expect(screen.getByLabelText(/repository url/i)).not.toBeNull();
    expect(screen.getByLabelText(/base branch \(optional\)/i)).not.toBeNull();
    // No local-destination field for a cloud project — nothing persists locally.
    expect(screen.queryByLabelText(/save in/i)).toBeNull();
  });

  it("submits the remote URL and base branch to the cloud creation endpoint", async () => {
    const user = userEvent.setup();
    vi.mocked(api.createCloudProject).mockResolvedValue(cloudProject());
    render(<ProjectWorkspace initialProjects={[]} renderedAt={new Date().toISOString()} />);

    await user.click(screen.getByRole("button", { name: /review a remote repository/i }));
    await user.type(screen.getByLabelText(/repository url/i), "https://github.com/acme/widgets.git");
    await user.type(screen.getByLabelText(/base branch \(optional\)/i), "develop");
    await user.click(screen.getByRole("button", { name: /^create$/i }));

    expect(api.createCloudProject).toHaveBeenCalledWith(
      "https://github.com/acme/widgets.git",
      "develop",
    );
  });
});
