/**
 * Card — the standard Paper Light panel.
 *
 * White surface, hairline border, optional header with a trailing slot. Every
 * grouped block in the product uses this so spacing stays consistent.
 */

import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

/**
 * Top-level panel. Uses `--radius-panel` (11px) — the widest radius in regular
 * use, so anything nested inside steps down the scale and reads as concentric.
 *
 * `overflow-hidden` is what lets a flush header clip cleanly to the corners.
 */
export function Card({ children, className = "" }: CardProps) {
  return (
    <section
      className={`overflow-hidden rounded-panel border border-line bg-paper ${className}`}
    >
      {children}
    </section>
  );
}

interface CardHeaderProps {
  title: ReactNode;
  /** Small icon rendered before the title. */
  icon?: ReactNode;
  /** Right-aligned metadata or actions. */
  aside?: ReactNode;
}

/**
 * Panel header. `flush-top` re-applies the parent's radius minus the 1px
 * border, so a header with its own background clips cleanly into the corners
 * instead of leaving a sliver of page showing through each one.
 */
export function CardHeader({ title, icon, aside }: CardHeaderProps) {
  return (
    <header className="flush-top flex items-center gap-2.5 border-b border-line px-[18px] py-3.5">
      {icon && <span className="text-ink-muted">{icon}</span>}
      <h2 className="text-[13px] font-semibold">{title}</h2>
      {aside && (
        <div className="numeric ml-auto text-[11.5px] font-normal text-ink-subtle">
          {aside}
        </div>
      )}
    </header>
  );
}

export function CardBody({ children, className = "" }: CardProps) {
  return <div className={`px-[18px] py-[18px] ${className}`}>{children}</div>;
}

/**
 * A labelled row inside a card body. Rows separate themselves with a hairline
 * rule, and the first and last row drop their outer padding so the card body
 * controls the overall inset.
 */
export function CardRow({
  label,
  hint,
  children,
}: {
  label: ReactNode;
  hint?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex items-center gap-3.5 border-b border-line py-3.5 first:pt-0 last:border-b-0 last:pb-0">
      <div className="min-w-0 flex-1">
        <p className="text-[13.5px] font-semibold">{label}</p>
        {hint && (
          <p className="mt-0.5 text-xs leading-relaxed text-ink-subtle">
            {hint}
          </p>
        )}
      </div>
      {children}
    </div>
  );
}
