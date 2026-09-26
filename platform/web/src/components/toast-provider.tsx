/**
 * Toast notifications — one queue for the whole app.
 *
 * Semantics (agreed design, see openspec/changes/friendly-error-messages):
 *
 * - FIFO capped at 3: a 4th push evicts the oldest entry immediately.
 * - Every toast owns a 10 s countdown; hovering pauses it and leaving resumes
 *   it for the *remaining* time (pause/resume, not reset).
 * - Rendered through a portal into `document.body` so no `overflow-hidden`
 *   ancestor can clip the stack; fixed bottom-right, away from the SaveBar.
 *
 * The queue lives in a plain-JS store rather than component state: timers,
 * countdown deadlines and `Date.now()` reads are impure, and keeping them out
 * of React's render path keeps both the compiler's purity rules and the
 * effect rules satisfied. React subscribes via `useSyncExternalStore`.
 *
 * Mounted once at the app root, inside `UiPreferenceProvider` (it translates).
 */

"use client";

import {
  createContext,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { useUiText } from "@/components/ui-preference-bootstrap";
import { Toast, type ToastTone } from "@/components/ui/toast";

const CAPACITY = 3;
const DISMISS_MS = 10_000;
const EXIT_MS = 300;

export interface ToastEntry {
  id: number;
  message: string;
  tone: ToastTone;
  leaving: boolean;
}

type Listener = () => void;

/** Plain-JS toast queue. One instance per app, module-scoped, no React deps. */
class ToastStore {
  private entries: (ToastEntry & { deadline: number | null; remainingMs: number })[] = [];
  private listeners = new Set<Listener>();
  private timers = new Map<number, ReturnType<typeof setTimeout>>();
  private nextId = 0;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  /** Snapshot must be referentially stable between mutations. */
  snapshot = (): ToastEntry[] => this.entries;

  private emit() {
    for (const listener of this.listeners) listener();
  }

  push = (message: string, tone: ToastTone = "error"): void => {
    const id = ++this.nextId;
    // FIFO eviction: the oldest entry goes, even if the user is hovering it.
    if (this.entries.length >= CAPACITY) {
      this.evict(this.entries[0].id);
    }
    this.entries = [
      ...this.entries,
      { id, message, tone, leaving: false, deadline: Date.now() + DISMISS_MS, remainingMs: 0 },
    ];
    this.timers.set(id, setTimeout(() => this.beginExit(id), DISMISS_MS));
    this.emit();
  };

  private evict(id: number) {
    const timer = this.timers.get(id);
    if (timer) clearTimeout(timer);
    this.timers.delete(id);
    this.entries = this.entries.filter((toast) => toast.id !== id);
  }

  private beginExit(id: number) {
    const timer = this.timers.get(id);
    if (timer) clearTimeout(timer);
    this.timers.delete(id);
    this.entries = this.entries.map((toast) =>
      toast.id === id ? { ...toast, leaving: true, deadline: null } : toast,
    );
    this.emit();
    // Drop from the DOM after the exit animation completes.
    setTimeout(() => {
      this.entries = this.entries.filter((toast) => toast.id !== id);
      this.emit();
    }, EXIT_MS);
  }

  /** Hover pause: freeze the countdown with the remaining time, not a reset. */
  pause = (id: number): void => {
    const toast = this.entries.find((item) => item.id === id);
    const timer = this.timers.get(id);
    if (!toast || !timer || toast.leaving) return;
    clearTimeout(timer);
    this.timers.delete(id);
    const remaining = Math.max(0, (toast.deadline ?? Date.now()) - Date.now());
    this.entries = this.entries.map((item) =>
      item.id === id ? { ...item, deadline: null, remainingMs: remaining } : item,
    );
    this.emit();
  };

  resume = (id: number): void => {
    const toast = this.entries.find((item) => item.id === id);
    if (!toast || toast.leaving) return;
    const delay = toast.remainingMs || DISMISS_MS;
    this.entries = this.entries.map((item) =>
      item.id === id ? { ...item, deadline: Date.now() + delay, remainingMs: 0 } : item,
    );
    this.timers.set(id, setTimeout(() => this.beginExit(id), delay));
    this.emit();
  };

  dismiss = (id: number): void => {
    this.evict(id);
    this.emit();
  };

  /** Test seam: drop every toast and timer without touching the listeners. */
  clear = (): void => {
    for (const timer of this.timers.values()) clearTimeout(timer);
    this.timers.clear();
    this.entries = [];
    this.emit();
  };
}

const store = new ToastStore();

/** Stable empty array: getServerSnapshot must return the same reference
 * every call, or useSyncExternalStore treats it as a change and loops. */
const EMPTY_TOASTS: ToastEntry[] = [];

type PushToast = (message: string, tone?: ToastTone) => void;

const ToastContext = createContext<{ push: PushToast }>({
  push: () => undefined,
});

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useUiText();
  // SSR renders no portal (the store starts empty), so the subscription is
  // client-only by construction and hydration stays consistent.
  const toasts = useSyncExternalStore(store.subscribe, store.snapshot, () => EMPTY_TOASTS);
  const value = useMemo(() => ({ push: store.push }), []);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {toasts.length > 0 &&
        createPortal(
          <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex flex-col items-end gap-2.5">
            {toasts.map((toast) => (
              <Toast
                key={toast.id}
                message={toast.message}
                tone={toast.tone}
                leaving={toast.leaving}
                dismissLabel={t("toast.dismiss")}
                onMouseEnter={() => store.pause(toast.id)}
                onMouseLeave={() => store.resume(toast.id)}
                onDismiss={() => store.dismiss(toast.id)}
              />
            ))}
          </div>,
          document.body,
        )}
    </ToastContext.Provider>
  );
}

/** Exposed for tests (and a future "clear all" affordance). */
export const toastStore = store;

export function useToast(): { push: PushToast } {
  return useContext(ToastContext);
}
