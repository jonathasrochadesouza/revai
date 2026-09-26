import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, type StatusResponse } from "@/lib/api";
import { ConnectionStore, DEBOUNCE_MS, problemFor } from "@/lib/connection-store";

function statusPayload(overrides: {
  verdict?: StatusResponse["ai"]["verdict"];
  ttl?: number;
}): StatusResponse {
  return {
    api: { status: "ok", app: "RevAI", version: "3.0.0", environment: "test" },
    ai: {
      active_provider_id: "anthropic",
      active_state: overrides.verdict === "ok" ? "ready" : "needs_auth",
      active_usable: overrides.verdict === "ok",
      active_version: null,
      active_detail: null,
      active_remediation: null,
      ready_provider_ids: overrides.verdict === "active_broken" ? ["ollama"] : [],
      unknown_provider_ids: [],
      total: 8,
      verdict: overrides.verdict ?? "ok",
    },
    checked_at: new Date().toISOString(),
    from_cache: false,
    ttl_s: overrides.ttl ?? 30,
  };
}

let store: ConnectionStore;

beforeEach(() => {
  store = new ConnectionStore();
  sessionStorage.clear();
});

afterEach(() => {
  store.reset();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("problem derivation", () => {
  it("reports nothing when everything is healthy", () => {
    expect(problemFor(statusPayload({ verdict: "ok" }))).toBeNull();
  });

  it("maps each AI verdict to its own problem kind", () => {
    expect(problemFor(statusPayload({ verdict: "active_broken" }))).toBe("ai_active_broken");
    expect(problemFor(statusPayload({ verdict: "none_ready" }))).toBe("ai_none_ready");
    expect(problemFor(statusPayload({ verdict: "unknown" }))).toBe("ai_unknown");
  });
});

describe("connection store", () => {
  it("reports nothing before the first answer", () => {
    expect(store.snapshot().phase).toBe("probing");
    expect(store.snapshot().problem).toBeNull();
  });

  it("stays silent when the first answer is healthy", async () => {
    vi.spyOn(api, "getStatus").mockResolvedValue(statusPayload({ verdict: "ok" }));

    await store.probe();

    expect(store.snapshot().phase).toBe("ready");
    expect(store.snapshot().problem).toBeNull();
  });

  it("does not announce a problem on its first observation", async () => {
    vi.spyOn(api, "getStatus").mockResolvedValue(statusPayload({ verdict: "none_ready" }));

    await store.probe();

    expect(store.snapshot().observed).toBe("ai_none_ready");
    expect(store.snapshot().problem).toBeNull();
  });

  it("announces a problem that is still there on the second observation", async () => {
    vi.spyOn(api, "getStatus").mockResolvedValue(statusPayload({ verdict: "none_ready" }));

    await store.probe();
    await store.refresh();

    expect(store.snapshot().problem).toBe("ai_none_ready");
  });

  it("never announces a failure that recovered inside the debounce window", async () => {
    const getStatus = vi
      .spyOn(api, "getStatus")
      .mockRejectedValueOnce(new Error("fetch failed"))
      .mockResolvedValue(statusPayload({ verdict: "ok" }));

    await store.probe();
    expect(store.snapshot().problem).toBeNull();

    await store.probe();

    expect(getStatus).toHaveBeenCalledTimes(2);
    expect(store.snapshot().problem).toBeNull();
    expect(store.snapshot().observed).toBeNull();
  });

  it("announces a backend that is still down after the debounce window", async () => {
    vi.spyOn(api, "getStatus").mockRejectedValue(new Error("fetch failed"));

    await store.probe();
    await store.probe();

    expect(store.snapshot().problem).toBe("api_down");
    expect(store.snapshot().unreachableReason).toBe("fetch failed");
  });

  it("surfaces a persistent problem on its own, without a user action", async () => {
    vi.spyOn(api, "getStatus").mockRejectedValue(new Error("fetch failed"));
    vi.useFakeTimers();

    await store.probe();
    expect(store.snapshot().problem).toBeNull();

    // The first observation schedules the follow-up probe; nothing else happens.
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 1);

    expect(store.snapshot().problem).toBe("api_down");
  });

  it("skips the round trip while the cached answer still holds", async () => {
    const getStatus = vi
      .spyOn(api, "getStatus")
      .mockResolvedValue(statusPayload({ verdict: "ok", ttl: 30 }));

    await store.probe();
    store.revalidateIfStale();
    store.revalidateIfStale();

    expect(getStatus).toHaveBeenCalledTimes(1);
  });

  it("revalidates once the cached answer has expired", async () => {
    const getStatus = vi
      .spyOn(api, "getStatus")
      .mockResolvedValue(statusPayload({ verdict: "ok", ttl: 0 }));

    await store.probe();
    store.revalidateIfStale();
    await vi.waitFor(() => expect(getStatus).toHaveBeenCalledTimes(2));
  });

  it("bypasses both caches on an explicit re-check", async () => {
    const getStatus = vi.spyOn(api, "getStatus").mockResolvedValue(statusPayload({ verdict: "ok" }));

    await store.probe();
    await store.refresh();

    expect(getStatus).toHaveBeenLastCalledWith(true);
  });
});

describe("dismissal", () => {
  it("hides the announced problem", async () => {
    vi.spyOn(api, "getStatus").mockResolvedValue(statusPayload({ verdict: "none_ready" }));
    await store.probe();
    await store.probe();
    expect(store.snapshot().problem).toBe("ai_none_ready");

    store.dismiss();

    expect(store.snapshot().problem).toBeNull();
  });

  it("keeps the dismissal across a fresh store reading the same session", async () => {
    vi.spyOn(api, "getStatus").mockResolvedValue(statusPayload({ verdict: "none_ready" }));
    await store.probe();
    await store.probe();
    store.dismiss();

    // A new store stands in for a navigation that remounted every component.
    const remounted = new ConnectionStore();
    await remounted.probe();
    await remounted.probe();

    expect(remounted.snapshot().problem).toBeNull();
    expect(remounted.snapshot().observed).toBe("ai_none_ready");
  });

  it("still warns about a different problem kind", async () => {
    const getStatus = vi.spyOn(api, "getStatus").mockRejectedValue(new Error("fetch failed"));
    await store.probe();
    await store.probe();
    store.dismiss();
    expect(store.snapshot().problem).toBeNull();

    getStatus.mockResolvedValue(statusPayload({ verdict: "active_broken" }));
    await store.probe();
    await store.probe();

    expect(store.snapshot().problem).toBe("ai_active_broken");
  });

  it("does not survive a new session", async () => {
    vi.spyOn(api, "getStatus").mockResolvedValue(statusPayload({ verdict: "none_ready" }));
    await store.probe();
    await store.probe();
    store.dismiss();

    sessionStorage.clear(); // a new tab starts with empty session storage
    const fresh = new ConnectionStore();
    await fresh.probe();
    await fresh.probe();

    expect(fresh.snapshot().problem).toBe("ai_none_ready");
  });
});
