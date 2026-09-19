/**
 * The Model API ⇄ Local CLI agent selector.
 *
 * Carried over from mock 07 and re-skinned: the active card is marked by a
 * near-black border rather than a coloured glow, because in Paper Light emphasis
 * comes from contrast.
 *
 * Implemented as a radiogroup so arrow keys move between options, which is what a
 * user expects from a two-way choice.
 */

"use client";

import { useUiText } from "@/components/ui-preference-bootstrap";
import type { EngineMode } from "@/lib/api";

interface Option {
  mode: EngineMode;
  titleKey: string;
  descriptionKey: string;
  badgeKey?: string;
  icon: React.ReactNode;
}

const EXTERNAL_LINK = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-3.5">
    <path d="M21 2 13 10M15 2h6v6M11 6H5a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-6" />
  </svg>
);

const TERMINAL = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-3.5">
    <rect x="2" y="4" width="20" height="16" rx="2" />
    <path d="m6 9 3 3-3 3M13 15h5" />
  </svg>
);

const OPTIONS: Option[] = [
  {
    mode: "api",
    titleKey: "engine.mode.api.title",
    descriptionKey: "engine.mode.api.description",
    badgeKey: "engine.mode.badge",
    icon: EXTERNAL_LINK,
  },
  {
    mode: "cli",
    titleKey: "engine.mode.cli.title",
    descriptionKey: "engine.mode.cli.description",
    icon: TERMINAL,
  },
];

interface ModeSelectorProps {
  value: EngineMode;
  onChange: (mode: EngineMode) => void;
}

export function ModeSelector({ value, onChange }: ModeSelectorProps) {
  const { t } = useUiText();
  return (
    <div role="radiogroup" aria-label={t("engine.modeAria")} className="grid gap-2.5 sm:grid-cols-2">
      {OPTIONS.map((option) => {
        const selected = option.mode === value;
        return (
          <button
            key={option.mode}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.mode)}
            // `cursor-default` on the active card is deliberate: a pointer implies
            // "this does something", and clicking the option you are already on
            // does nothing.
            className={`rounded-card border p-4 text-left transition-colors ${
              selected
                ? "cursor-default border-ink shadow-[0_0_0_1px_var(--color-ink)]"
                : "cursor-pointer border-line hover:border-line-strong hover:bg-canvas"
            }`}
          >
            <div className="mb-2 flex items-center gap-2.5">
              <span
                className={`grid size-7 shrink-0 place-items-center rounded-chip border ${
                  selected ? "border-ink bg-ink text-paper" : "border-line bg-canvas text-ink-muted"
                }`}
              >
                {option.icon}
              </span>
              <b className="text-[13.5px] font-semibold">{t(option.titleKey)}</b>
              <span
                aria-hidden
                className={`ml-auto size-4 shrink-0 rounded-full ${
                  selected ? "border-[5px] border-ink" : "border-[1.5px] border-line-strong"
                }`}
              />
            </div>
            <p className="text-[12.5px] leading-relaxed text-ink-muted">{t(option.descriptionKey)}</p>
            {option.badgeKey && (
              <span className="mt-2.5 inline-block rounded-chip border border-success-line bg-success-surface px-[7px] py-[3px] text-[10px] font-semibold uppercase tracking-wide text-success">
                {t(option.badgeKey)}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
