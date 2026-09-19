import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

import { BackendUnreachable, buildTroubleshootingPrompt } from "@/components/backend-unreachable";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("buildTroubleshootingPrompt", () => {
  it("interpolates the reason and names the compose service, port and health route", () => {
    const prompt = buildTroubleshootingPrompt("GET /api/config failed with 503");

    expect(prompt).toContain("Technical detail: GET /api/config failed with 503");
    expect(prompt).toContain("`api`");
    expect(prompt).toContain("http://127.0.0.1:8799/api/health");
    expect(prompt).toContain("docker compose logs api --tail=100");
  });
});

describe("BackendUnreachable", () => {
  it("never renders the AI troubleshooting prompt into the DOM", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<BackendUnreachable reason="GET /api/config failed with 503" apiBaseUrl="http://127.0.0.1:8799" />);

    // The prompt (agent-facing) must never leak into screen text. The two
    // user-facing compose commands DO render, as the recovery hint.
    expect(screen.queryByText(/Technical detail:/)).toBeNull();
    expect(document.body.textContent).not.toContain("Diagnose why the RevAI api service");
    expect(document.body.textContent).toContain("docker compose ps");

    fireEvent.click(screen.getByText("Copy AI troubleshooting prompt"));
    await vi.waitFor(() => {
      expect(writeText).toHaveBeenCalledTimes(1);
    });
    // Wait for the transient "Copied" confirmation before asserting content.
    expect(await screen.findByText("Copied")).not.toBeNull();
    const copied = writeText.mock.calls[0][0] as string;
    expect(copied).toContain("docker compose logs api --tail=100");
    expect(copied).toContain("Technical detail: GET /api/config failed with 503");
    expect(copied).toContain("Diagnose why the RevAI api service");
    // The copy feedback names the action, never the prompt itself.
    expect(document.body.textContent).not.toContain("Diagnose why the RevAI api service");
  });

  it("offers a Try again action wired to the router refresh", () => {
    render(<BackendUnreachable reason="network down" apiBaseUrl="http://127.0.0.1:8799" />);

    fireEvent.click(screen.getByText("Try again"));
    expect(refresh).toHaveBeenCalledTimes(1);
  });
});
