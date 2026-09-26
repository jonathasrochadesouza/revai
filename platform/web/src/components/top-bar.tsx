/**
 * The application top bar: wordmark, breadcrumb, and a right-hand slot for
 * status chips. Sticky, with a hairline bottom border.
 */

"use client";

import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { ConnectionBanner } from "@/components/connection-banner";
import { Wordmark } from "@/components/logo";
import { useUiText } from "@/components/ui-preference-bootstrap";
import { Loader } from "@/components/ui/loader";

/**
 * The documentation site is a separate Docusaurus deployment, not a route in
 * this app — override at build time if it is hosted elsewhere.
 */
const DOCS_SITE_URL = process.env.NEXT_PUBLIC_DOCS_URL ?? "http://127.0.0.1:3001";

/** A breadcrumb entry. A bare string renders as plain text (a catalog key is translated); add `href` to link it, or `menu` to turn it into a dropdown. */
export type Crumb =
  | string
  | { label: string; href: string }
  | { label: string; menu: { label: string; href: string }[] };

/**
 * The settings sub-pages, shared by the breadcrumb and the primary-nav dropdown.
 *
 * One list, two surfaces: a settings page added here appears in both, and cannot
 * appear in one while missing from the other.
 */
export const SETTINGS_MENU: { label: string; href: string }[] = [
  { label: "common.engine", href: "/settings/engine" },
  { label: "common.apiAndAi", href: "/settings/connection" },
  { label: "common.skillsPrompts", href: "/settings/skills" },
  { label: "common.appearance", href: "/settings/appearance" },
  { label: "common.data", href: "/settings/data" },
];

/**
 * Top-level destinations.
 *
 * Deliberately short: settings sub-pages live in the dropdown only. `Data` and
 * `Appearance` used to appear in both places, which made the header longer without
 * making anything easier to find.
 */
const PRIMARY_NAV: { label: string; href: string; external?: boolean }[] = [
  { label: "common.projects", href: "/" },
  { label: "common.insights", href: "/insights" },
  { label: "common.docs", href: DOCS_SITE_URL, external: true },
];

/**
 * A navigation link that shows a small spinner while the target route is
 * pending. Without it a slow server render looks frozen and users keep
 * clicking the same tab.
 */
function NavLink({
  href,
  className,
  role,
  ariaCurrent,
  onClick,
  external,
  children,
}: {
  href: string;
  className: string;
  role?: string;
  ariaCurrent?: "page";
  onClick?: () => void;
  external?: boolean;
  children: ReactNode;
}) {
  const { pending } = useLinkStatus();
  if (external) {
    // A separately deployed site: a full navigation, not a client-side route,
    // so `next/link`'s prefetch/pending machinery does not apply here.
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        role={role}
        onClick={onClick}
        className={`inline-flex items-center gap-1.5 ${className}`}
      >
        {children}
      </a>
    );
  }
  return (
    <Link
      href={href}
      role={role}
      aria-current={ariaCurrent}
      aria-busy={pending}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 ${className}`}
    >
      {pending ? <Loader variant="spinner" size="sm" className="shrink-0" /> : null}
      {children}
    </Link>
  );
}

interface NavDropdownProps {
  label: string;
  items: { label: string; href: string }[];
  /** Current pathname, used to mark the active entry. */
  current: string;
  variant: "breadcrumb" | "nav";
  align: "left" | "right";
}

/** A trigger that opens a small link menu, used for the Settings entries. */
function NavDropdown({ label, items, current, variant, align }: NavDropdownProps) {
  const { t } = useUiText();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Same dismissal contract as InfoTooltip: outside pointerdown and Escape,
  // with focus returned to the trigger so keyboard users keep their place.
  useEffect(() => {
    if (!open) return;
    const dismissOutside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const dismissWithEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("pointerdown", dismissOutside);
    document.addEventListener("keydown", dismissWithEscape);
    return () => {
      document.removeEventListener("pointerdown", dismissOutside);
      document.removeEventListener("keydown", dismissWithEscape);
    };
  }, [open]);

  // The breadcrumb trigger mirrors the plain crumb link (semibold ink with a
  // hover underline) so the affordance comes from the shared styling, not from
  // an added caret.
  const trigger =
    variant === "breadcrumb"
      ? "flex shrink-0 items-center rounded-xs font-semibold text-ink transition-colors hover:text-low hover:underline"
      : "flex items-center rounded-control px-2.5 py-1.5 text-[12px] font-medium text-ink-muted transition-colors hover:bg-canvas hover:text-ink";

  return (
    <span ref={rootRef} className="relative shrink-0">
      <button
        type="button"
        ref={triggerRef}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        className={trigger}
      >
        {t(label)}
      </button>
      {open && (
        <div
          role="menu"
          className={`absolute top-full z-30 mt-1.5 grid min-w-36 overflow-hidden rounded-control border border-line-strong bg-paper p-1 shadow-sm ${align === "right" ? "right-0" : "left-0"}`}
        >
          {items.map((item) => {
            const active = item.href === current;
            return (
              <NavLink
                key={item.href}
                href={item.href}
                role="menuitem"
                ariaCurrent={active ? "page" : undefined}
                onClick={() => setOpen(false)}
                className={`w-full rounded-chip px-3 py-2 text-[12px] font-medium transition-colors ${active ? "bg-canvas text-ink" : "text-ink-muted hover:bg-canvas hover:text-ink"}`}
              >
                {t(item.label)}
              </NavLink>
            );
          })}
        </div>
      )}
    </span>
  );
}

interface TopBarProps {
  /** Breadcrumb trail. The last entry always renders as the current page. */
  breadcrumb?: Crumb[];
  children?: ReactNode;
}

export function TopBar({ breadcrumb = [], children }: TopBarProps) {
  const { t } = useUiText();
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-paper">
      <div className="mx-auto flex h-14 min-w-0 max-w-[1180px] items-center gap-3 px-4 sm:gap-[18px] sm:px-7">
        <Wordmark />

        {breadcrumb.length > 0 && (
          <>
            <span aria-hidden className="hidden h-[18px] w-px bg-line-strong sm:block" />
            <nav
              aria-label={t("common.breadcrumb")}
              className="flex min-w-0 flex-1 items-center gap-2.5 text-[13.5px] text-ink-muted"
            >
              {breadcrumb.map((crumb, index) => {
                const isLast = index === breadcrumb.length - 1;
                // Only crumbs that are neither first nor last collapse on narrow
                // screens — the current page (last) must always stay visible.
                const isMiddle = index > 0 && !isLast;
                const isObject = typeof crumb === "object";
                const isMenu = isObject && "menu" in crumb;
                const rawLabel = isObject ? crumb.label : crumb;
                const label = t(rawLabel);
                const href = isObject && "href" in crumb ? crumb.href : undefined;
                const menu = isMenu ? crumb.menu : undefined;

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
                    ) : menu ? (
                      <NavDropdown
                        label={rawLabel}
                        items={menu}
                        current={pathname}
                        variant="breadcrumb"
                        align="left"
                      />
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
          aria-label={t("common.primaryNavigation")}
          className="ml-auto hidden items-center gap-1 md:flex"
        >
          {PRIMARY_NAV.map((item) => (
            <NavLink
              key={item.href}
              href={item.href}
              external={item.external}
              className="rounded-control px-2.5 py-1.5 text-[12px] font-medium text-ink-muted transition-colors hover:bg-canvas hover:text-ink"
            >
              {t(item.label)}
            </NavLink>
          ))}
          <NavDropdown
            label="common.settings"
            items={SETTINGS_MENU}
            current={pathname}
            variant="nav"
            align="right"
          />
        </nav>

        <details className="ml-auto shrink-0 md:hidden">
          <summary className="cursor-pointer list-none rounded-control border border-line-strong px-2.5 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink">
            {t("common.menu")}
          </summary>
          {/* The same destinations as the wide layout, from the same two lists. */}
          <nav aria-label={t("common.primaryNavigation")} className="absolute right-5 top-[52px] z-30 grid min-w-40 overflow-hidden rounded-control border border-line-strong bg-paper p-1 shadow-sm">
            {[...PRIMARY_NAV, ...SETTINGS_MENU].map((item) =>
              "external" in item && item.external ? (
                <a
                  key={item.href}
                  href={item.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-chip px-3 py-2 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink"
                >
                  {t(item.label)}
                </a>
              ) : (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-chip px-3 py-2 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink"
                >
                  {t(item.label)}
                </Link>
              ),
            )}
          </nav>
        </details>

        {children && (
          <div className="flex items-center gap-2.5">{children}</div>
        )}
      </div>

      {/* Below the navigation row but inside the sticky header, so a connection
          problem stays visible while the page scrolls. Renders nothing at all
          while probing or healthy. */}
      <ConnectionBanner />
    </header>
  );
}
