/**
 * Connection status provider.
 *
 * Mounted once in the root layout — the only component that survives navigation —
 * so the first probe, the debounce and the dismissal all outlive a route change.
 * The banner itself renders inside `TopBar` (below the navigation row, inside the
 * sticky header) and reads this context.
 */

"use client";

import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";

import {
  connectionStore,
  type ConnectionSnapshot,
  type ProblemKind,
} from "@/lib/connection-store";

export interface ConnectionContextValue extends ConnectionSnapshot {
  refresh: () => Promise<void>;
  dismiss: () => void;
}

/**
 * Stable server snapshot: returning a fresh object here would never satisfy
 * `Object.is` between renders and would loop `useSyncExternalStore`.
 */
const SERVER_SNAPSHOT: ConnectionSnapshot = {
  phase: "probing",
  status: null,
  unreachableReason: null,
  observed: null,
  problem: null,
  refreshing: false,
};

const ConnectionContext = createContext<ConnectionContextValue>({
  ...SERVER_SNAPSHOT,
  refresh: async () => undefined,
  dismiss: () => undefined,
});

export function ConnectionProvider({ children }: { children: ReactNode }) {
  const snapshot = useSyncExternalStore(
    connectionStore.subscribe,
    connectionStore.snapshot,
    () => SERVER_SNAPSHOT,
  );
  const pathname = usePathname();

  // First probe, plus a re-read after any action that can change the answer. Both
  // are external-system subscriptions, which is exactly what effects are for.
  useEffect(() => {
    void connectionStore.probe();
    const stale = () => void connectionStore.refresh();
    window.addEventListener("revai:connection-stale", stale);
    return () => window.removeEventListener("revai:connection-stale", stale);
  }, []);

  // Navigation revalidates, but only when the cached answer has expired — inside the
  // TTL the backend would return the identical payload, so the request is skipped.
  useEffect(() => {
    connectionStore.revalidateIfStale();
  }, [pathname]);

  // The snapshot is referentially stable between mutations, so consumers only
  // re-render when the status actually changes.
  const value = useMemo(
    () => ({ ...snapshot, refresh: connectionStore.refresh, dismiss: connectionStore.dismiss }),
    [snapshot],
  );

  return <ConnectionContext.Provider value={value}>{children}</ConnectionContext.Provider>;
}

export function useConnection(): ConnectionContextValue {
  return useContext(ConnectionContext);
}

export type { ProblemKind };
