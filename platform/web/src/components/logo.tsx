/**
 * The RevAI mark — a bolt in a near-black rounded square.
 *
 * Deliberately not a colour: in Paper Light the brand reads as ink, and colour
 * is reserved for meaning.
 */

import Link from "next/link";

export function Logo({ size = 26 }: { size?: number }) {
  return (
    <span
      className="grid shrink-0 place-items-center rounded-chip bg-ink"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="#fff"
        strokeWidth={2.5}
        strokeLinejoin="round"
        style={{ width: size * 0.54, height: size * 0.54 }}
      >
        <path d="M13 2 3 14h8l-1 8 10-12h-8l1-8z" />
      </svg>
    </span>
  );
}

/**
 * The wordmark as a link home.
 *
 * A clickable logo returning to the root is a convention users reach for without
 * thinking, so it gets a real `<Link>` — keyboard focus, middle-click to open in a
 * new tab, and a visible focus ring all come for free.
 */
export function Wordmark({ href = "/" }: { href?: string }) {
  return (
    <Link
      href={href}
      aria-label="RevAI — go to the dashboard"
      className="flex shrink-0 items-center gap-2.5 rounded-control px-1 py-0.5 -mx-1 transition-colors hover:bg-canvas"
    >
      <Logo />
      <span className="text-[14.5px] font-bold tracking-[-0.3px]">RevAI</span>
    </Link>
  );
}
