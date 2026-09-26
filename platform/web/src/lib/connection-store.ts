/**
 * Connection status: one plain-JS store, read by the banner and the API & AI screen.
 *
 * Why a store rather than component state: every route renders its own `TopBar`
 * (including the `loading.tsx` skeletons), so top-bar state is destroyed on each
 * navigation — probing would restart and a dismissal would be undone. The state
 * therefore lives outside React, exactly like the toast queue, and React subscribes
 * through `useSyncExternalStore`.
 *
 * Three behaviours are deliberate and specified:
 *
 *  * **Nothing is reported before the first answer.** `phase` stays `"probing"`, and
 *    the banner renders no element at all — not even a placeholder — so the page
 *    never shifts after load.
 *  * **A problem must be confirmed before it warns.** Restarting the backend is
 *    routine; a banner that flashes on every restart trains users to ignore it. A
 *    problem is announced only on its second consecutive observation, or after
 *    `DEBOUNCE_MS` of continuous failure, whichever comes first.
 *  * **Dismissal is per problem kind, per session.** Dismissing "backend down" must
 *    not silence "provider needs auth" that appears later, and a new tab starts
 *    clean.
 */

import { api, type StatusResponse } from "@/lib/api";

/** The kinds of problem the banner can announce, in precedence order. */
export type ProblemKind =
  | "api_down"
  | "ai_active_broken"
  | "ai_none_ready"
  | "ai_unknown";

export interface ConnectionSnapshot {
  phase: "probing" | "ready";
  /** The last successful payload, or null while the backend is unreachable. */
  status: StatusResponse | null;
  /** Developer-facing reason for an unreachable backend, shown as technical detail. */
  unreachableReason: string | null;
  /** The problem observed right now, before debounce and dismissal. */
  observed: ProblemKind | null;
  /** The problem the banner should show: confirmed, not dismissed. */
  problem: ProblemKind | null;
  /** True while an explicit re-check is in flight. */
  refreshing: boolean;
}

export const DEBOUNCE_MS = 3_000;
const DISMISSED_KEY = "revai:connection-dismissed";

/**
 * Which problem, if any, a payload represents.
 */
export function problemFor(status: StatusResponse): ProblemKind | null {
  if (status.ai.verdict === "active_broken") return "ai_active_broken";
  if (status.ai.verdict === "none_ready") return "ai_none_ready";
  if (status.ai.verdict === "unknown") return "ai_unknown";
  return null;
}

type Listener = () => void;

const PROBING: ConnectionSnapshot = {
  phase: "probing",
  status: null,
  unreachableReason: null,
  observed: null,
  problem: null,
  refreshing: false,
};

export class ConnectionStore {
  private snapshotValue: ConnectionSnapshot = PROBING;
  private listeners = new Set<Listener>();
  private pending: ProblemKind | null = null;
  private confirmed: ProblemKind | null = null;
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private inFlight: Promise<void> | null = null;
  private cachedUntil = 0;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  /** Referentially stable between mutations, as `useSyncExternalStore` requires. */
  snapshot = (): ConnectionSnapshot => this.snapshotValue;

  private emit() {
    for (const listener of this.listeners) listener();
  }

  private set(patch: Partial<ConnectionSnapshot>) {
    this.snapshotValue = { ...this.snapshotValue, ...patch };
    this.emit();
  }

  /** Probe once. Concurrent callers share the in-flight request. */
  probe = (refresh = false): Promise<void> => {
    if (this.inFlight && !refresh) return this.inFlight;
    if (refresh) this.set({ refreshing: true });

    const run = api.getStatus(refresh).then(
      (status) => {
        // A server-side cache of `ttl_s` means a revalidation before that is
        // guaranteed to return the same answer, so we skip the round trip entirely.
        this.cachedUntil = Date.now() + status.ttl_s * 1000;
        this.observe(problemFor(status), { status, unreachableReason: null });
      },
      (cause: unknown) => {
        this.cachedUntil = 0;
        this.observe("api_down", {
          status: null,
          unreachableReason: cause instanceof Error ? cause.message : String(cause),
        });
      },
    );

    this.inFlight = run.finally(() => {
      this.inFlight = null;
      if (refresh) this.set({ refreshing: false });
    });
    return this.inFlight;
  };

  /** Explicit user re-check: bypasses both caches. */
  refresh = (): Promise<void> => {
    this.cachedUntil = 0;
    return this.probe(true);
  };

  /** Called on navigation: cheap, and a no-op while the cached answer still holds. */
  revalidateIfStale = (): void => {
    if (Date.now() < this.cachedUntil) return;
    void this.probe();
  };

  /**
   * Fold one observation into the debounce state machine.
   *
   * A problem is announced on its *second consecutive* observation. The first
   * observation schedules a follow-up probe `DEBOUNCE_MS` later, so a failure that
   * persists still surfaces without any user action, while one that recovered inside
   * the window never shows at all.
   */
  private observe(kind: ProblemKind | null, payload: Partial<ConnectionSnapshot>) {
    if (kind === null) {
      this.clearDebounce();
      this.confirmed = null;
      this.pending = null;
      this.set({ ...payload, phase: "ready", observed: null, problem: null });
      return;
    }

    if (kind === this.confirmed || kind === this.pending) {
      this.confirmed = kind;
      this.pending = null;
      this.clearDebounce();
    } else {
      // A new problem kind — including one appearing right after a recovery —
      // starts its own confirmation window.
      this.confirmed = null;
      this.pending = kind;
      this.scheduleConfirmation();
    }

    this.set({
      ...payload,
      phase: "ready",
      observed: kind,
      problem: this.confirmed && !this.isDismissed(this.confirmed) ? this.confirmed : null,
    });
  }

  private scheduleConfirmation() {
    this.clearDebounce();
    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null;
      // Re-probe rather than trusting the stale reading: if the backend came back
      // within the window, this observation clears the problem instead of showing it.
      this.cachedUntil = 0;
      void this.probe();
    }, DEBOUNCE_MS);
  }

  private clearDebounce() {
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    this.debounceTimer = null;
  }

  /** Hide the current problem kind for this session only. */
  dismiss = (): void => {
    const kind = this.snapshotValue.problem;
    if (!kind) return;
    const dismissed = new Set(this.readDismissed());
    dismissed.add(kind);
    this.writeDismissed([...dismissed]);
    this.set({ problem: null });
  };

  private isDismissed(kind: ProblemKind): boolean {
    return this.readDismissed().includes(kind);
  }

  private readDismissed(): ProblemKind[] {
    // `sessionStorage` is unavailable during SSR and can throw when a browser
    // blocks storage; a failure to read a dismissal must never break the app.
    try {
      const raw = globalThis.sessionStorage?.getItem(DISMISSED_KEY);
      return raw ? (JSON.parse(raw) as ProblemKind[]) : [];
    } catch {
      return [];
    }
  }

  private writeDismissed(kinds: ProblemKind[]) {
    try {
      globalThis.sessionStorage?.setItem(DISMISSED_KEY, JSON.stringify(kinds));
    } catch {
      // Nothing to recover: the banner simply reappears on the next observation.
    }
  }

  /** Test seam: forget everything, including timers and dismissals. */
  reset = (): void => {
    this.clearDebounce();
    this.snapshotValue = PROBING;
    this.pending = null;
    this.confirmed = null;
    this.inFlight = null;
    this.cachedUntil = 0;
    try {
      globalThis.sessionStorage?.removeItem(DISMISSED_KEY);
    } catch {
      // Storage is optional; nothing depends on the removal succeeding.
    }
    this.emit();
  };
}

export const connectionStore = new ConnectionStore();

/** Ask every listener to re-read the status after an action that can change it. */
export function markConnectionStale(): void {
  window.dispatchEvent(new Event("revai:connection-stale"));
}
