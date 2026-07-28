/**
 * NumberControl — a numeric input that cannot invent a value.
 *
 * The naive version of this control was a plain `<input type="number">` whose
 * `onChange` did `Number(event.target.value)`. That has a bug the user hits
 * immediately: **`Number("") === 0`**. Clearing the field to retype it silently
 * writes `0` into the document, and since `0` is not a legal budget, saving fails
 * with `Input should be greater than 0` — an error about a value the user never
 * typed.
 *
 * The fix is to stop pretending the input holds a number. It holds *text*, which is
 * only committed upward when it actually parses:
 *
 *   * an empty field is a legitimate mid-typing state, so nothing is committed
 *   * on blur, an empty or unparseable field snaps back to the last good value
 *   * a value below `min` **is** committed and flagged inline, because `0` typed
 *     deliberately is a real intent and silently clamping it would be a lie
 */

"use client";

import { useState } from "react";

const CONTROL =
  "w-full rounded-control border border-line-strong bg-paper py-2.5 font-mono text-[12.5px] text-ink outline-none transition-shadow placeholder:text-ink-subtle focus:border-ink focus:shadow-[0_0_0_3px_rgba(9,9,11,0.06)] disabled:bg-canvas disabled:text-ink-subtle";

interface NumberControlProps {
  id: string;
  /** The committed value, owned by the parent. */
  value: number | null;
  min: number;
  step: number;
  disabled?: boolean;
  placeholder?: string;
  /** Unit marker rendered inside the field, e.g. `$`. Decorative, not editable. */
  prefix?: string;
  /** Trailing unit, e.g. `tokens`. */
  suffix?: string;
  "aria-label"?: string;
  onCommit: (value: number) => void;
}

export function NumberControl({
  id,
  value,
  min,
  step,
  disabled = false,
  placeholder,
  prefix,
  suffix,
  onCommit,
  ...rest
}: NumberControlProps) {
  const [text, setText] = useState(() => (value === null ? "" : String(value)));

  // Track the last value seen from the parent so an external change — save, discard,
  // or switching to unlimited — is reflected in the field. This is React's documented
  // "adjust state when a prop changes" pattern: it runs during render and re-renders
  // immediately, which is cheaper and less surprising than an effect that would first
  // paint the stale text.
  const [lastExternal, setLastExternal] = useState(value);
  if (value !== lastExternal) {
    setLastExternal(value);
    setText(value === null ? "" : String(value));
  }

  const parsed = text.trim() === "" ? null : Number(text);
  const belowMin = parsed !== null && Number.isFinite(parsed) && parsed < min;

  return (
    <>
      <div className="relative">
        {prefix && (
          <span
            aria-hidden
            className={`pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 font-mono text-[12.5px] ${
              disabled ? "text-ink-subtle" : "text-ink-muted"
            }`}
          >
            {prefix}
          </span>
        )}

        <input
          {...rest}
          id={id}
          type="number"
          inputMode="decimal"
          min={min}
          step={step}
          disabled={disabled}
          placeholder={placeholder}
          value={text}
          onChange={(event) => {
            const raw = event.target.value;
            setText(raw);

            // Commit only a real number. An empty field means "still typing", not zero.
            const next = raw.trim() === "" ? null : Number(raw);
            if (next !== null && Number.isFinite(next)) {
              setLastExternal(next);
              onCommit(next);
            }
          }}
          onBlur={() => {
            // Leaving the field empty would otherwise show nothing while the document
            // still holds the previous value — a mismatch between what is displayed and
            // what would be saved.
            if (text.trim() === "" || !Number.isFinite(Number(text))) {
              setText(value === null ? "" : String(value));
            }
          }}
          className={`${CONTROL} numeric ${prefix ? "pl-7" : "pl-3"} ${
            suffix ? "pr-16" : "pr-3"
          } ${belowMin ? "border-critical-line" : ""}`}
        />

        {suffix && (
          <span
            aria-hidden
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-ink-subtle"
          >
            {suffix}
          </span>
        )}
      </div>

      {belowMin && (
        <p className="mt-1.5 text-[11.5px] text-critical">
          Must be at least {min}. The backend rejects anything lower.
        </p>
      )}
    </>
  );
}
