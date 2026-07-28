/**
 * The application top bar: wordmark, breadcrumb, and a right-hand slot for
 * status chips. Sticky, with a hairline bottom border.
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { Wordmark } from "@/components/logo";

/** A breadcrumb entry. A bare string renders as plain text; add `href` to link it. */
export type Crumb = string | { label: string; href: string };

interface TopBarProps {
  /** Breadcrumb trail. The last entry always renders as the current page. */
  breadcrumb?: Crumb[];
  children?: ReactNode;
}

export function TopBar({ breadcrumb = [], children }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-paper">
      <div className="mx-auto flex h-14 max-w-[1180px] items-center gap-[18px] px-7">
        <Wordmark />

        {breadcrumb.length > 0 && (
          <>
            <span aria-hidden className="h-[18px] w-px bg-line-strong" />
            <nav
              aria-label="Breadcrumb"
              className="flex items-center gap-2.5 text-[13.5px] text-ink-muted"
            >
              {breadcrumb.map((crumb, index) => {
                const isLast = index === breadcrumb.length - 1;
                const label = typeof crumb === "string" ? crumb : crumb.label;
                const href = typeof crumb === "string" ? undefined : crumb.href;

                return (
                  <span key={label} className="flex items-center gap-2.5">
                    {index > 0 && (
                      <svg
                        aria-hidden
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={2}
                        className="size-3 text-ink-subtle"
                      >
                        <polyline points="9 18 15 12 9 6" />
                      </svg>
                    )}
                    {isLast ? (
                      // The current page is not a link — nothing to navigate to.
                      <span aria-current="page">{label}</span>
                    ) : href ? (
                      <Link
                        href={href}
                        className="rounded-xs font-semibold text-ink transition-colors hover:text-low hover:underline"
                      >
                        {label}
                      </Link>
                    ) : (
                      <span className="font-semibold text-ink">{label}</span>
                    )}
                  </span>
                );
              })}
            </nav>
          </>
        )}

        {children && (
          <div className="ml-auto flex items-center gap-2.5">{children}</div>
        )}
      </div>
    </header>
  );
}
