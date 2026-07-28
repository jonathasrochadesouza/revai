/**
 * Switch — an on/off control in the Paper Light language.
 *
 * A real `<button role="switch">` rather than a styled checkbox, so screen
 * readers announce the state and the keyboard works without extra handlers.
 */

"use client";

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  /** Accessible name. Required — an unlabelled switch is unusable non-visually. */
  label: string;
  disabled?: boolean;
}

export function Switch({ checked, onChange, label, disabled = false }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-[22px] w-[38px] shrink-0 rounded-full transition-colors disabled:opacity-40 ${
        checked ? "bg-ink" : "bg-line-strong"
      }`}
    >
      <span
        aria-hidden
        className={`absolute top-[3px] size-4 rounded-full bg-paper shadow-sm transition-[left] ${
          checked ? "left-[19px]" : "left-[3px]"
        }`}
      />
    </button>
  );
}
