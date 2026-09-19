"use client";

import { Info } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

export function InfoTooltip({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const tooltipId = useId();
  const rootRef = useRef<HTMLSpanElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

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

  return (
    <span
      ref={rootRef}
      className="relative inline-flex"
      onPointerEnter={() => setOpen(true)}
      onPointerLeave={() => {
        if (!rootRef.current?.contains(document.activeElement)) setOpen(false);
      }}
      onFocusCapture={() => setOpen(true)}
      onBlurCapture={(event) => {
        if (!rootRef.current?.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-describedby={open ? tooltipId : undefined}
        onClick={() => setOpen(true)}
        className="rounded-chip p-0.5 text-ink-subtle transition-colors hover:bg-canvas hover:text-ink focus-visible:text-ink"
      >
        <Info className="size-3" aria-hidden="true" />
      </button>
      {open ? (
        <span
          id={tooltipId}
          role="tooltip"
          className="absolute left-0 top-full z-50 mt-1.5 w-64 rounded-control border border-line-strong bg-ink px-3 py-2 text-left text-[11px] font-normal leading-relaxed text-paper shadow-xl"
        >
          {children}
        </span>
      ) : null}
    </span>
  );
}
