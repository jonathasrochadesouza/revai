/**
 * Loader — Paper Light.
 *
 * Indeterminate progress indicators for navigations and slow fetches, so the
 * user always knows the app is working. All variants draw from the semantic
 * tokens only: hairline strokes, ink emphasis, no gradients, no blur.
 *
 * Variants:
 *   spinner  — hairline ring with an ink arc (the default; reads at any size)
 *   dots     — three ink dots rising in turn
 *   snake    — a short ink bar sweeping a hairline track
 *   skeleton — pulsing paper blocks previewing the page layout
 *
 * `DEFAULT_LOADER_VARIANT` switches the product-wide look in one line.
 */

"use client";

import { useUiText } from "@/components/ui-preference-bootstrap";

export type LoaderVariant = "spinner" | "dots" | "snake" | "skeleton";

export const DEFAULT_LOADER_VARIANT: LoaderVariant = "spinner";

export type LoaderSize = "sm" | "md" | "lg";

const SPINNER: Record<LoaderSize, string> = {
  sm: "size-3.5 border-2",
  md: "size-6 border-2",
  lg: "size-9 border-[3px]",
};

const DOTS: Record<LoaderSize, string> = {
  sm: "size-1 gap-1",
  md: "size-1.5 gap-1.5",
  lg: "size-2 gap-2",
};

const SNAKE: Record<LoaderSize, string> = {
  sm: "w-24 h-1",
  md: "w-40 h-1",
  lg: "w-56 h-1.5",
};

interface LoaderProps {
  variant?: LoaderVariant;
  size?: LoaderSize;
  className?: string;
}

export function Loader({ variant = DEFAULT_LOADER_VARIANT, size = "md", className = "" }: LoaderProps) {
  if (variant === "dots") {
    return (
      <span role="status" className={`inline-flex items-center ${DOTS[size]} ${className}`} aria-label="Loading">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="loader-dot rounded-full bg-ink motion-reduce:opacity-60"
            style={{ animationDelay: `${index * 0.15}s` }}
          />
        ))}
      </span>
    );
  }

  if (variant === "snake") {
    return (
      <span
        role="status"
        aria-label="Loading"
        className={`inline-flex overflow-hidden rounded-full border border-line bg-sunken ${SNAKE[size]} ${className}`}
      >
        <span className="loader-snake h-full w-1/3 rounded-full bg-ink motion-reduce:opacity-60" />
      </span>
    );
  }

  if (variant === "skeleton") {
    return (
      <div role="status" aria-label="Loading" className={`w-full max-w-[560px] space-y-3.5 ${className}`}>
        <div className="h-2.5 w-24 animate-pulse rounded-xs bg-sunken" />
        <div className="h-7 w-72 max-w-full animate-pulse rounded-xs bg-sunken" />
        <div className="surface space-y-2.5 p-5">
          <div className="h-2.5 w-1/2 animate-pulse rounded-xs bg-sunken" />
          <div className="h-2.5 w-2/3 animate-pulse rounded-xs bg-sunken" />
          <div className="h-2.5 w-1/3 animate-pulse rounded-xs bg-sunken" />
        </div>
      </div>
    );
  }

  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-line border-t-ink motion-reduce:animate-none ${SPINNER[size]} ${className}`}
    />
  );
}

/**
 * Centered composition for route `loading.tsx`: the loader plus an eyebrow
 * caption. Rendered inside the page frame, so the top bar stays visible while
 * the route fetches its server data.
 */
export function LoadingPanel({ variant }: { variant?: LoaderVariant }) {
  const { t } = useUiText();
  return (
    <div className="grid min-h-[65vh] w-full place-items-center px-5">
      <div className="flex flex-col items-center gap-3.5">
        <Loader variant={variant ?? DEFAULT_LOADER_VARIANT} />
        <p className="eyebrow">{t("Loading")}</p>
      </div>
    </div>
  );
}
