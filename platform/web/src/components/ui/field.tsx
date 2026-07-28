/**
 * Form primitives — Paper Light.
 *
 * Labels are wired to inputs with real `htmlFor`/`id` pairs rather than nesting,
 * so clicking a label focuses its control and screen readers announce the name.
 */

import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

const CONTROL =
  "w-full rounded-control border border-line-strong bg-paper px-3 py-2.5 font-mono text-[12.5px] text-ink outline-none transition-shadow placeholder:text-ink-subtle focus:border-ink focus:shadow-[0_0_0_3px_rgba(9,9,11,0.06)] disabled:bg-canvas disabled:text-ink-subtle";

interface FieldProps {
  label: string;
  htmlFor: string;
  /** Right-aligned annotation, e.g. "stored with chmod 600". */
  note?: ReactNode;
  hint?: ReactNode;
  children: ReactNode;
}

export function Field({ label, htmlFor, note, hint, children }: FieldProps) {
  return (
    <div className="mb-3.5 last:mb-0">
      <div className="mb-[7px] flex items-center gap-2">
        <label htmlFor={htmlFor} className="text-[12.5px] font-medium text-ink-muted">
          {label}
        </label>
        {note && <span className="ml-auto text-[11px] text-ink-subtle">{note}</span>}
      </div>
      {children}
      {hint && (
        <p className="mt-[7px] text-[11.5px] leading-relaxed text-ink-subtle">{hint}</p>
      )}
    </div>
  );
}

export function TextInput({ className = "", ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${CONTROL} ${className}`} {...rest} />;
}

export function Select({
  className = "",
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={`${CONTROL} cursor-pointer ${className}`} {...rest}>
      {children}
    </select>
  );
}

/**
 * A number input for currency and counts.
 *
 * `inputMode="decimal"` gets the right keyboard on touch devices, and the value
 * stays monospaced so figures line up between rows.
 */
export function NumberInput({
  className = "",
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="number"
      inputMode="decimal"
      className={`${CONTROL} numeric ${className}`}
      {...rest}
    />
  );
}
