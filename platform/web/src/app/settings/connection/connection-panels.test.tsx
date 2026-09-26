import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectionPanels, RUN_BACKEND_DOC } from "@/app/settings/connection/connection-panels";
import type { ConnectionContextValue } from "@/components/connection-provider";
import type { StatusResponse } from "@/lib/api";

const connection = vi.hoisted(() => ({ current: null as ConnectionContextValue | null }));

// The recovery screen offers a retry, which calls `useRouter().refresh()`; the app
// router is not mounted under a bare `render`.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
  usePathname: () => "/settings/connection",
}));
vi.mock("@/components/connection-provider", () => ({
  useConnection: () => connection.current,
}));

function status(overrides: {
  ai?: Partial<StatusResponse["ai"]>;
  checked_at?: string;
}): StatusResponse {
  return {
    api: { status: "ok", app: "RevAI", version: "3.0.0-alpha.0", environment: "test" },
    ai: {
      active_provider_id: "anthropic",
      active_state: "ready",
      active_usable: true,
      active_version: null,
      active_detail: null,
      active_remediation: null,
      ready_provider_ids: ["anthropic", "ollama"],
      unknown_provider_ids: [],
      total: 8,
      verdict: "ok",
      ...overrides.ai,
    },
    checked_at: overrides.checked_at ?? "2026-09-22T14:30:00.000Z",
    from_cache: false,
    ttl_s: 30,
  };
}

function mount(value: Partial<ConnectionContextValue>) {
  connection.current = {
    phase: "ready",
    status: status({}),
    unreachableReason: null,
    observed: null,
    problem: null,
    refreshing: false,
    refresh: vi.fn().mockResolvedValue(undefined),
    dismiss: vi.fn(),
    ...value,
  } as ConnectionContextValue;
  return render(<ConnectionPanels />);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("connection panels", () => {
  it("shows a busy state before the first answer", () => {
    mount({ phase: "probing", status: null });

    expect(screen.getByText("Checking the connection…")).not.toBeNull();
  });

  it("reports the backend version, address and environment", () => {
    const { container } = mount({});

    expect(container.textContent).toContain("3.0.0-alpha.0");
    expect(container.textContent).toContain("http://127.0.0.1:8799");
    expect(container.textContent).toContain("test");
    expect(screen.getByText("API connected")).not.toBeNull();
  });

  it("shows the ready-of-total scoreboard and names the ready providers", () => {
    const { container } = mount({});

    expect(container.textContent).toContain("2 of 8 ready");
    expect(container.textContent).toContain("Ready: Anthropic, Ollama (local)");
  });

  it("shows the remediation verbatim for a broken provider", () => {
    const { container } = mount({
      status: status({
        ai: {
          active_state: "needs_auth",
          active_usable: false,
          active_detail: "No API key stored.",
          active_remediation: "revai config set anthropic.key",
          ready_provider_ids: [],
          verdict: "none_ready",
        },
      }),
    });

    expect(container.textContent).toContain("revai config set anthropic.key");
    expect(container.textContent).toContain("No API key stored.");
    expect(container.textContent).toContain("None of the providers reported itself ready.");
  });

  it("lists providers whose state could not be confirmed", () => {
    const { container } = mount({
      status: status({ ai: { unknown_provider_ids: ["copilot_cli"] } }),
    });

    expect(container.textContent).toContain("Could not be confirmed: GitHub Copilot CLI");
  });

  it("re-checks on demand and reports the collection time", () => {
    const refresh = vi.fn().mockResolvedValue(undefined);
    const { container } = mount({ refresh });

    expect(container.textContent).toContain("Checked at");
    fireEvent.click(screen.getByText("Check again"));

    expect(refresh).toHaveBeenCalledOnce();
  });

  it("disables the re-check control while it is in flight", () => {
    mount({ refreshing: true });

    expect(screen.getByText("Checking…").hasAttribute("disabled")).toBe(true);
  });

  it("links to the engine screen and to the backend startup documentation", () => {
    mount({});

    const targets = screen.getAllByRole("link").map((link) => link.getAttribute("href"));
    expect(targets).toContain("/settings/engine");
    expect(targets).toContain(RUN_BACKEND_DOC);
  });

  it("renders the recovery screen when the backend is unreachable", () => {
    const { container } = mount({ status: null, unreachableReason: "fetch failed" });

    expect(screen.getByText("Backend unreachable")).not.toBeNull();
    expect(container.textContent).toContain("uv run revai-api");
    expect(container.textContent).toContain("fetch failed");
    expect(screen.getByText("Try again")).not.toBeNull();
  });
});
