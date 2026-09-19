/**
 * Toast — a single floating notification.
 *
 * The base surface is theme-INDEPENDENT (see `--color-toast-*` in
 * globals.css): it always inverts against the page so it reads as floating
 * above it, in both light and dark. Severity comes from a thin left accent
 * bar in a semantic colour plus an icon — never from the surface colour.
 */

"use client";

import type { ReactNode } from "react";

export type ToastTone = "info" | "error" | "success";

const ACCENTS: Record<ToastTone, string> = {
  info: "var(--color-info)",
  error: "var(--color-critical)",
  success: "var(--color-success)",
};

const ICONS: Record<ToastTone, ReactNode> = {
  info: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px]">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </svg>
  ),
  error: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px]">
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
  success: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="size-[15px]">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
};

interface ToastProps {
  message: string;
  tone: ToastTone;
  /** Pausing the countdown on hover is handled by the provider. */
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onDismiss: () => void;
  /** False while the exit animation plays. */
  leaving?: boolean;
  /** Accessibility label for the dismiss button. */
  dismissLabel: string;
}

export function Toast({
  message,
  tone,
  onMouseEnter,
  onMouseLeave,
  onDismiss,
  leaving = false,
  dismissLabel,
}: ToastProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={`pointer-events-auto relative flex w-[320px] items-start gap-2.5 overflow-hidden rounded-panel border px-3.5 py-3 shadow-[0_12px_32px_-10px_rgba(0,0,0,0.35)] transition-[opacity,transform] duration-300 ease-out ${
        leaving ? "translate-x-6 opacity-0" : "translate-x-0 opacity-100"
      }`}
      style={{
        backgroundColor: "var(--color-toast-bg)",
        color: "var(--color-toast-ink)",
      }}
    >
      {/* Severity accent — a hairline rail on the leading edge. */}
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-[3px]"
        style={{ backgroundColor: ACCENTS[tone] }}
      />
      <span className="mt-px shrink-0" style={{ color: ACCENTS[tone] }}>
        {ICONS[tone]}
      </span>
      <p className="min-w-0 flex-1 text-[12.5px] leading-relaxed">{message}</p>
      <button
        type="button"
        onClick={onDismiss}
        aria-label={dismissLabel}
        className="shrink-0 rounded-xs p-0.5 opacity-60 transition-opacity hover:opacity-100"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-3.5">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}
