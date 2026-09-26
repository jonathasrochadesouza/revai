import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConnectionBanner, CONNECTION_HREF } from "@/components/connection-banner";
import type { ConnectionContextValue } from "@/components/connection-provider";
import type { StatusResponse } from "@/lib/api";

let pathname = "/";
const connection = vi.hoisted(() => ({ current: null as ConnectionContextValue | null }));

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@/components/connection-provider", () => ({
  useConnection: () => connection.current,
}));

function status(overrides: Partial<StatusResponse["ai"]> = {}): StatusResponse {
  return {
    api: { status: "ok", app: "RevAI", version: "3.0.0", environment: "test" },
    ai: {
      active_provider_id: "anthropic",
      active_state: "needs_auth",
      active_usable: false,
      active_version: null,
      active_detail: null,
      active_remediation: null,
      ready_provider_ids: [],
      unknown_provider_ids: [],
      total: 8,
      verdict: "none_ready",
      ...overrides,
    },
    checked_at: new Date().toISOString(),
    from_cache: false,
    ttl_s: 30,
  };
}

function mount(value: Partial<ConnectionContextValue>) {
  connection.current = {
    phase: "ready",
    status: status(),
    unreachableReason: null,
    observed: null,
    problem: null,
    refreshing: false,
    refresh: async () => undefined,
    dismiss: vi.fn(),
    ...value,
  } as ConnectionContextValue;
  return render(<ConnectionBanner />);
}

function banner(): HTMLElement | null {
  return screen.queryByRole("status");
}

beforeEach(() => {
  pathname = "/";
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("connection banner", () => {
  it("renders no element while probing", () => {
    mount({ phase: "probing", status: null });

    expect(banner()).toBeNull();
  });

  it("renders no element when healthy", () => {
    mount({ problem: null });

    expect(banner()).toBeNull();
  });

  it("announces an unreachable backend", () => {
    mount({ problem: "api_down", status: null, unreachableReason: "fetch failed" });

    expect(banner()?.textContent).toContain("cannot reach its local backend");
  });

  it("names the ready alternative when the configured provider is broken", () => {
    mount({
      problem: "ai_active_broken",
      status: status({ verdict: "active_broken", ready_provider_ids: ["ollama"] }),
    });

    const text = banner()?.textContent ?? "";
    expect(text).toContain("Anthropic needs attention");
    expect(text).toContain("Ollama (local) is ready");
  });

  it("states plainly that no provider is ready", () => {
    mount({ problem: "ai_none_ready" });

    expect(banner()?.textContent).toContain("No AI provider is ready");
  });

  it("says the state could not be confirmed rather than claiming a failure", () => {
    mount({
      problem: "ai_unknown",
      status: status({ active_provider_id: "copilot_cli", verdict: "unknown" }),
    });

    const text = banner()?.textContent ?? "";
    expect(text).toContain("could not be confirmed");
    expect(text).toContain("GitHub Copilot CLI");
  });

  it("offers one action that leads to the connection screen", () => {
    mount({ problem: "ai_none_ready" });

    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(1);
    expect(links[0].getAttribute("href")).toBe(CONNECTION_HREF);
  });

  it("is polite to screen readers rather than interrupting", () => {
    mount({ problem: "ai_none_ready" });

    expect(banner()?.getAttribute("aria-live")).toBe("polite");
  });

  it("dismisses through a labelled control", () => {
    const dismiss = vi.fn();
    mount({ problem: "ai_none_ready", dismiss });

    fireEvent.click(screen.getByLabelText("Dismiss connection warning"));

    expect(dismiss).toHaveBeenCalledOnce();
  });

  it("stays out of the way on the connection screen", () => {
    pathname = CONNECTION_HREF;
    mount({ problem: "api_down", status: null });

    expect(banner()).toBeNull();
  });
});
