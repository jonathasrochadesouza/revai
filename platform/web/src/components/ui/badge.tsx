/**
 * Badge — the severity and status pill used across every screen.
 *
 * The severity variants are the canonical mapping for the whole product:
 * critical is red, medium is amber, low is blue. Defined once here so no screen
 * can invent its own.
 */

import type { ReactNode } from "react";

export type BadgeTone =
  | "neutral"
  | "critical"
  | "medium"
  | "low"
  | "success"
  | "info";

const TONES: Record<BadgeTone, string> = {
  neutral: "bg-canvas text-ink-muted border-line",
  critical: "bg-critical-surface text-critical border-critical-line",
  medium: "bg-medium-surface text-medium border-medium-line",
  low: "bg-low-surface text-low border-low-line",
  success: "bg-success-surface text-success border-success-line",
  info: "bg-info-surface text-info border-low-line",
};

interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
  /** Render a leading dot. Use for live or connection state. */
  dot?: boolean;
  className?: string;
}

export function Badge({
  children,
  tone = "neutral",
  dot = false,
  className = "",
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${TONES[tone]} ${className}`}
    >
      {dot && (
        <span
          aria-hidden
          className="size-1.5 rounded-full bg-current"
        />
      )}
      {children}
    </span>
  );
}
