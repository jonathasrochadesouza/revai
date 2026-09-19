/**
 * Button — Paper Light.
 *
 * Emphasis comes from contrast, not colour: the primary variant is near-black,
 * not a brand hue. `rounded-control` keeps it one step below panel radius so a
 * button inside a card reads as concentric.
 */

import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-ink text-paper border-ink hover:bg-ink-hover",
  secondary: "bg-paper text-ink border-line-strong hover:bg-canvas",
  ghost: "bg-transparent text-ink-muted border-transparent hover:bg-canvas hover:text-ink",
  danger:
    "bg-paper text-critical border-critical-line hover:bg-critical-surface",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: Variant;
  icon?: ReactNode;
}

export function Button({
  children,
  variant = "secondary",
  icon,
  className = "",
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-control border px-4 py-2 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}
