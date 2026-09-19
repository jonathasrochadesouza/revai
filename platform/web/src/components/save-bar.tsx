/**
 * The save action bar.
 *
 * Sticky at the bottom so it stays reachable on a long settings page. The button
 * says what it does — "Save changes" — and never names the file behind it:
 * knowing that state lives in a YAML file is documentation, not an action label.
 *
 * While the auto-save preference is still undecided (`auto_save === null` on the
 * saved config), the bar also offers to save automatically. "No, don't ask
 * again" is the same preference set to `false`, so one value covers both
 * "off" and "never show this offer again", and the offer text points at
 * Settings › Appearance where it can be turned on later.
 *
 * With auto-save enabled the manual buttons go away — saving is the background
 * behaviour, not an action — and the bar only reports progress. They return if
 * a save fails, so a failed auto-save can still be retried by hand.
 *
 * The "All changes saved" confirmation is a receipt, not a resident: it holds
 * on screen for three seconds, then slides out to the left and unmounts. A
 * lasting "saved" bar trains the user to ignore it, and an instant snap away
 * reads as a flicker — so the hold gives it time to be seen and the glide makes
 * the dismissal read as intentional. Errors are never auto-dismissed: a
 * failure stays until the user acts on it.
 *
 * It renders nothing when there is nothing to save, rather than showing a
 * disabled button: an empty bar occupying screen space is worse than no bar.
 */

"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useUiText } from "@/components/ui-preference-bootstrap";

/** How long the saved receipt stays readable before it starts leaving. */
const HOLD_MS = 3000;
/** How long the slide-out transition itself runs. */
const EXIT_MS = 550;

type Status = "idle" | "saving" | "saved" | "error";

interface SaveBarProps {
  dirty: boolean;
  status: Status;
  /** Human summary of what is pending, e.g. "3 unsaved changes". */
  summary: string;
  /** Populated when `status === "error"`. */
  error?: string | null;
  /** The saved auto-save preference; `null` means never answered. */
  autoSave: boolean | null;
  /** Answer the auto-save offer; the caller persists the decision. */
  onSetAutoSave: (value: boolean) => void;
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
  autoSave,
  onSetAutoSave,
  onSave,
  onDiscard,
}: SaveBarProps) {
  const { t } = useUiText();
  const saving = status === "saving";
  const autoSaving = autoSave === true;
  const offer = dirty && autoSave === null;

  // Lifecycle of the saved receipt: hold, then exit, then gone. Every state
  // change happens inside a timer callback — the react-hooks rule (rightly)
  // forbids synchronous setState in the effect body — and the render derives
  // the phase so a stale receipt can never make the bar flicker when a save
  // lands or the user resumes editing: with "saved" status an unanswered
  // receipt simply defaults to "hold", and a non-saved status ignores the
  // receipt entirely. A fresh save always gets its full three seconds because
  // the timers are cleared and restarted on every status change.
  const [receipt, setReceipt] = useState<"hold" | "exit" | "gone" | null>(null);

  useEffect(() => {
    if (status !== "saved") {
      // Reset off the synchronous path; the tick is invisible because the
      // render above no longer consults a receipt once the status has moved.
      const reset = setTimeout(() => setReceipt(null), 0);
      return () => clearTimeout(reset);
    }
    const leave = setTimeout(() => setReceipt("exit"), HOLD_MS);
    const gone = setTimeout(() => setReceipt("gone"), HOLD_MS + EXIT_MS);
    return () => {
      clearTimeout(leave);
      clearTimeout(gone);
    };
  }, [status]);

  const phase =
    status !== "saved" ? null : receipt === "gone" ? null : (receipt ?? "hold");

  // Nothing pending, nothing to report, and the receipt has finished leaving —
  // stay out of the way.
  if (!dirty && status !== "error" && phase === null) {
    return null;
  }

  const { icon, message } = describe(status, summary, error, autoSaving, t);

  // With auto-save on, saving is the background behaviour — the only reason to
  // surface a manual button is a failure the user needs to push through.
  const manualActions =
    (!autoSaving && dirty) || (autoSaving && status === "error");

  return (
    <div
      role="status"
      aria-live="polite"
      className={`sticky bottom-5 mt-4 flex flex-col gap-3 rounded-panel border border-line-strong bg-paper px-[18px] py-3.5 shadow-[0_8px_26px_-12px_rgba(0,0,0,0.22)] transition-[opacity,transform] duration-500 ease-out ${
        phase === "exit" ? "-translate-x-10 opacity-0" : "translate-x-0 opacity-100"
      }`}
    >
      <div className="flex flex-wrap items-center gap-3.5">
        <span className="flex items-center gap-2.5 text-[12.5px] text-ink-muted">
          {icon}
          {message}
        </span>

        {manualActions && (
          <div className="ml-auto flex gap-2.5">
            {!autoSaving && (
              <Button variant="ghost" onClick={onDiscard} disabled={saving}>
                {t("save.discard")}
              </Button>
            )}
            <Button variant="primary" onClick={onSave} disabled={saving} icon={SAVE}>
              {saving ? t("save.saving") : t("save.saveChanges")}
            </Button>
          </div>
        )}
      </div>

      {offer && (
        <div className="@container flex flex-col gap-2.5 border-t border-line pt-3">
          {/* Container-query layout: while the bar has room the copy sits left
              of the buttons and wraps within its own line box; on a narrow bar
              it stacks above them, everything centred horizontally. */}
          <div className="flex flex-col items-center gap-2.5 text-center @sm:flex-row @sm:justify-between @sm:gap-3 @sm:text-left">
            <p className="text-[12px] leading-relaxed text-ink-muted @sm:min-w-0 @sm:flex-1">
              {t("save.autoSaveOffer")}
            </p>
            <div className="flex flex-wrap justify-center gap-2.5 @sm:shrink-0">
              <Button
                variant="ghost"
                onClick={() => onSetAutoSave(false)}
                disabled={saving}
              >
                {t("save.autoSaveDecline")}
              </Button>
              <Button onClick={() => onSetAutoSave(true)} disabled={saving}>
                {t("save.autoSaveEnable")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function describe(
  status: Status,
  summary: string,
  error?: string | null,
  autoSaving = false,
  translate?: (key: string) => string,
) {
  const t = translate ?? ((key: string) => key);
  switch (status) {
    case "saved":
      return { icon: CHECK, message: t("save.allChangesSaved") };
    case "error":
      return { icon: ALERT, message: error ?? t("save.couldNotSave") };
    case "saving":
      return { icon: WARNING, message: t("save.saving") };
    default:
      return {
        icon: WARNING,
        message: autoSaving ? t("save.changesSaveAutomatically") : summary,
      };
  }
}
