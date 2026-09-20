/**
 * SkillsTab — marketplace gallery + installed skills interactions.
 *
 * The API module is mocked: these tests cover the UI contract (what the user
 * sees and which client calls an interaction issues), not the network layer.
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  searchMarketplace: vi.fn(),
  previewSkill: vi.fn(),
  installSkill: vi.fn(),
  updateSkill: vi.fn(),
  refreshSkill: vi.fn(),
  checkSkillUpdates: vi.fn(),
  uninstallSkill: vi.fn(),
  getConfig: vi.fn().mockResolvedValue({ config: { ui: { locale: "en-US" } } }),
}));

vi.mock("@/lib/api", () => ({ api }));

import { SkillsTab } from "./skills-tab";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const INSTALLED = {
  id: "code-review",
  source: "mattpocock/skills",
  name: "code-review",
  description: "Two-axis review",
  focus: "both" as const,
  enabled: true,
  body: "Review the diff carefully.",
  content_sha256: "a".repeat(64),
  license: "MIT",
  installs: 586_435,
  source_url: "https://github.com/mattpocock/skills",
  installed_at: "2026-09-20T00:00:00Z",
  updated_at: "2026-09-20T00:00:00Z",
};

const SEARCH_RESULT = {
  id: "security-audit",
  name: "security-audit",
  source: "acme/skills",
  installs: 10_000,
  description: "Security-focused review guidance.",
  url: "https://skills.sh/skill/acme/skills/security-audit",
};

async function search(term: string) {
  api.searchMarketplace.mockResolvedValue({ query: term, skills: [SEARCH_RESULT] });
  fireEvent.change(screen.getByPlaceholderText(/Search skills\.sh/), {
    target: { value: term },
  });
  fireEvent.click(screen.getByText("Search"));
  await screen.findByText("security-audit");
}

describe("SkillsTab", () => {
  it("renders installed skills with their focus badge and enabled switch", () => {
    render(<SkillsTab initial={[INSTALLED]} />);

    expect(screen.getAllByText("code-review").length).toBeGreaterThan(0);
    // The focus appears both as the row badge and as select options.
    expect(screen.getAllByText("Review + fix").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("true");
    expect(screen.getByText("mattpocock/skills · code-review")).not.toBeNull();
  });

  it("shows the empty state when nothing is installed", () => {
    render(<SkillsTab initial={[]} />);

    expect(screen.getByText("No skills installed yet")).not.toBeNull();
    expect(screen.queryByText("Check for updates")).toBeNull();
  });

  it("toggling a skill issues an updateSkill call", async () => {
    api.updateSkill.mockResolvedValue({ ...INSTALLED, enabled: false });

    render(<SkillsTab initial={[INSTALLED]} />);
    fireEvent.click(screen.getByRole("switch"));

    await waitFor(() => {
      expect(api.updateSkill).toHaveBeenCalledWith("code-review", { enabled: false });
    });
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("false");
  });

  it("uninstalling removes the row after the confirm dialog", async () => {
    api.uninstallSkill.mockResolvedValue(undefined);

    render(<SkillsTab initial={[INSTALLED]} />);
    fireEvent.click(screen.getByText("Uninstall"));

    expect(screen.getByText('Uninstall “code-review”?')).not.toBeNull();
    // The dialog's confirm button is the last Uninstall button in the DOM.
    const buttons = screen.getAllByText("Uninstall");
    fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => {
      expect(api.uninstallSkill).toHaveBeenCalledWith("code-review");
    });
    expect(screen.queryByText("mattpocock/skills · code-review")).toBeNull();
  });

  it("searches the marketplace on submit and hydrates results", async () => {
    render(<SkillsTab initial={[INSTALLED]} />);
    await search("security");

    expect(api.searchMarketplace).toHaveBeenCalledWith("security");
    expect(screen.getByText("Security-focused review guidance.")).not.toBeNull();
  });

  it("install flow previews the body and calls installSkill with the chosen focus", async () => {
    api.previewSkill.mockResolvedValue({
      id: "security-audit",
      name: "security-audit",
      source: "acme/skills",
      description: "Security-focused review guidance.",
      body: "Never flag style issues.",
      content_sha256: "b".repeat(64),
      license: "MIT",
      path: "skills/security-audit/SKILL.md",
      source_url: "https://github.com/acme/skills",
    });
    api.installSkill.mockResolvedValue({
      ...INSTALLED,
      id: "security-audit",
      name: "security-audit",
      source: "acme/skills",
    });

    render(<SkillsTab initial={[INSTALLED]} />);
    await search("security");

    // The install button lives on the marketplace row.
    fireEvent.click(screen.getByText("Install"));
    // The dialog pins the exact body into the DOM before install unlocks.
    expect(await screen.findByText("Never flag style issues.")).not.toBeNull();

    const dialog = screen.getByRole("dialog");
    const focusSelect = within(dialog).getByLabelText("Applies to");
    fireEvent.change(focusSelect, { target: { value: "review" } });
    fireEvent.click(screen.getByText("Install skill"));

    await waitFor(() => {
      expect(api.installSkill).toHaveBeenCalledWith({
        source: "acme/skills",
        skill_id: "security-audit",
        focus: "review",
      });
    });
  });
});
