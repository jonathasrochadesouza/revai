/**
 * The application top bar: wordmark, breadcrumb, and a right-hand slot for
 * status chips. Sticky, with a hairline bottom border.
 */

"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Wordmark } from "@/components/logo";
import { useUiText } from "@/components/ui-preference-bootstrap";

/** A breadcrumb entry. A bare string renders as plain text; add `href` to link it. */
export type Crumb = string | { label: string; href: string };

interface TopBarProps {
  /** Breadcrumb trail. The last entry always renders as the current page. */
  breadcrumb?: Crumb[];
  children?: ReactNode;
}

export function TopBar({ breadcrumb = [], children }: TopBarProps) {
  const { t } = useUiText();
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-paper">
      <div className="mx-auto flex h-14 min-w-0 max-w-[1180px] items-center gap-3 px-4 sm:gap-[18px] sm:px-7">
        <Wordmark />

        {breadcrumb.length > 0 && (
          <>
            <span aria-hidden className="hidden h-[18px] w-px bg-line-strong sm:block" />
            <nav
              aria-label={t("Breadcrumb")}
              className="flex min-w-0 flex-1 items-center gap-2.5 overflow-hidden text-[13.5px] text-ink-muted"
            >
              {breadcrumb.map((crumb, index) => {
                const isLast = index === breadcrumb.length - 1;
                // Only crumbs that are neither first nor last collapse on narrow
                // screens — the current page (last) must always stay visible.
                const isMiddle = index > 0 && !isLast;
                const label = t(typeof crumb === "string" ? crumb : crumb.label);
                const href = typeof crumb === "string" ? undefined : crumb.href;

                return (
                  <span
                    key={`${label}-${index}`}
                    className={`min-w-0 items-center gap-2.5 ${
                      isMiddle ? "hidden sm:flex" : "flex"
                    } ${isLast ? "min-w-0 flex-1" : "shrink-0"}`}
                  >
                    {index > 0 && (
                      <svg
                        aria-hidden
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={2}
                        className="size-3 shrink-0 text-ink-subtle"
                      >
                        <polyline points="9 18 15 12 9 6" />
                      </svg>
                    )}
                    {isLast ? (
                      // The current page is not a link — nothing to navigate to.
                      <span aria-current="page" className="truncate">
                        {label}
                      </span>
                    ) : href ? (
                      <Link
                        href={href}
                        className="shrink-0 truncate rounded-xs font-semibold text-ink transition-colors hover:text-low hover:underline"
                      >
                        {label}
                      </Link>
                    ) : (
                      <span className="shrink-0 truncate font-semibold text-ink">{label}</span>
                    )}
                  </span>
                );
              })}
            </nav>
          </>
        )}

        <nav
          aria-label={t("Primary navigation")}
          className="ml-auto hidden items-center gap-1 md:flex"
        >
          <Link href="/" className="rounded-control px-2.5 py-1.5 text-[12px] font-medium text-ink-muted transition-colors hover:bg-canvas hover:text-ink">
            {t("Projects")}
          </Link>
          <Link href="/insights" className="rounded-control px-2.5 py-1.5 text-[12px] font-medium text-ink-muted transition-colors hover:bg-canvas hover:text-ink">
            {t("Insights")}
          </Link>
          <Link href="/settings/data" className="rounded-control px-2.5 py-1.5 text-[12px] font-medium text-ink-muted transition-colors hover:bg-canvas hover:text-ink">
            {t("Data")}
          </Link>
          <Link href="/settings/appearance" className="rounded-control px-2.5 py-1.5 text-[12px] font-medium text-ink-muted transition-colors hover:bg-canvas hover:text-ink">
            {t("Appearance")}
          </Link>
          <Link href="/settings/engine" className="rounded-control px-2.5 py-1.5 text-[12px] font-medium text-ink-muted transition-colors hover:bg-canvas hover:text-ink">
            {t("Settings")}
          </Link>
        </nav>

        <details className="ml-auto shrink-0 md:hidden">
          <summary className="cursor-pointer list-none rounded-control border border-line-strong px-2.5 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink">
            {t("Menu")}
          </summary>
          <nav aria-label={t("Primary navigation")} className="absolute right-5 top-[52px] z-30 grid min-w-40 overflow-hidden rounded-control border border-line-strong bg-paper p-1 shadow-sm">
            <Link href="/" className="rounded-chip px-3 py-2 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink">{t("Projects")}</Link>
            <Link href="/insights" className="rounded-chip px-3 py-2 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink">{t("Insights")}</Link>
            <Link href="/settings/data" className="rounded-chip px-3 py-2 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink">{t("Data")}</Link>
            <Link href="/settings/appearance" className="rounded-chip px-3 py-2 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink">{t("Appearance")}</Link>
            <Link href="/settings/engine" className="rounded-chip px-3 py-2 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink">{t("Settings")}</Link>
          </nav>
        </details>

        {children && (
          <div className="flex items-center gap-2.5">{children}</div>
        )}
      </div>
    </header>
  );
}
