/**
 * The "Save to config.yaml" action bar.
 *
 * Carried over from mock 07. Sticky at the bottom so it stays reachable on a long
 * settings page, and it names the actual file — part of the promise that state is
 * plain YAML the user owns.
 *
 * It renders nothing when there is nothing to save, rather than showing a disabled
 * button: an empty bar occupying screen space is worse than no bar.
 */

"use client";

import { Button } from "@/components/ui/button";

type Status = "idle" | "saving" | "saved" | "error";

interface SaveBarProps {
  dirty: boolean;
  status: Status;
  /** Human summary, e.g. "3 unsaved changes". */
  summary: string;
  /** Populated when `status === "error"`. */
  error?: string | null;
  filename: string;
  onSave: () => void;
  onDiscard: () => void;
}

const WARNING = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px] text-medium">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 8v5M12 16h.01" />
  </svg>
);

const CHECK = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="size-[15px] text-success">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const ALERT = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px] text-critical">
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
  </svg>
);

const SAVE = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} className="size-[15px]">
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
    <polyline points="17 21 17 13 7 13 7 21" />
  </svg>
);

export function SaveBar({
  dirty,
  status,
  summary,
  error,
  filename,
  onSave,
  onDiscard,
}: SaveBarProps) {
  const saving = status === "saving";

  // Nothing pending and nothing to report — stay out of the way.
  if (!dirty && status !== "saved" && status !== "error") {
    return null;
  }

  const { icon, message } = describe(status, summary, error);

  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky bottom-5 mt-4 flex flex-wrap items-center gap-3.5 rounded-panel border border-line-strong bg-paper px-[18px] py-3.5 shadow-[0_8px_26px_-12px_rgba(0,0,0,0.22)]"
    >
      <span className="flex items-center gap-2.5 text-[12.5px] text-ink-muted">
        {icon}
        {message}
      </span>

      {dirty && (
        <div className="ml-auto flex gap-2.5">
          <Button variant="ghost" onClick={onDiscard} disabled={saving}>
            Discard
          </Button>
          <Button variant="primary" onClick={onSave} disabled={saving} icon={SAVE}>
            {saving ? "Saving…" : `Save to ${filename}`}
          </Button>
        </div>
      )}
    </div>
  );
}

function describe(status: Status, summary: string, error?: string | null) {
  switch (status) {
    case "saved":
      return { icon: CHECK, message: `Saved to ${summary}` };
    case "error":
      return { icon: ALERT, message: error ?? "Could not save" };
    default:
      return { icon: WARNING, message: summary };
  }
}
