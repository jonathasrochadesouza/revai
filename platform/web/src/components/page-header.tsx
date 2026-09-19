"use client";

import { useUiText } from "@/components/ui-preference-bootstrap";

type SettingsPage = "appearance" | "engine" | "data";

const TITLES: Record<SettingsPage, string> = {
  appearance: "settings.appearance.title",
  engine: "settings.engine.title",
  data: "data.title",
};

const SUBTITLES: Record<SettingsPage, string> = {
  appearance: "settings.appearance.subtitle",
  engine: "settings.engine.subtitle.before",
  data: "data.subtitle",
};

/** Page intro for the settings sub-pages, rendered server-side and translated client-side. */
export function SettingsPageHeader({ page }: { page: SettingsPage }) {
  const { t } = useUiText();
  return (
    <div className="mb-7">
      <p className="eyebrow mb-2">{t("settings.eyebrow")}</p>
      <h1 className="mb-2.5 text-[26px] font-bold tracking-[-0.7px]">{t(TITLES[page])}</h1>
      <p className="max-w-[70ch] text-[14px] leading-relaxed text-ink-muted">{t(SUBTITLES[page])}</p>
    </div>
  );
}

/** Page intro for the review setup route. */
export function ReviewPageHeader() {
  const { t } = useUiText();
  return (
    <div>
      <p className="eyebrow mb-2">{t("review.eyebrow")}</p>
      <h1 className="mb-2 text-[26px] font-bold tracking-[-0.7px]">
        {t("review.setupTitle")}
      </h1>
      <p className="max-w-[68ch] text-[14px] leading-relaxed text-ink-muted">
        {t("review.setupSubtitle")}
      </p>
    </div>
  );
}

type NoticeVariant = "appearance" | "engine" | "data";

const NOTICE_TITLES: Record<NoticeVariant, string> = {
  appearance: "settings.appearance.unavailable",
  engine: "settings.engine.configurationUnavailable",
  data: "data.unavailable",
};

/**
 * Unreachable-backend panel for the settings and review routes.
 *
 * The distinction matters: a 422 means the YAML is broken and the message names
 * the field, whereas a network failure means the process is not running.
 */
export function UnavailableNotice({
  variant,
  reason,
  hint,
}: {
  variant: NoticeVariant | "review";
  reason: string;
  hint?: string;
}) {
  const { t } = useUiText();
  return (
    <div className="surface border-critical-line bg-critical-surface px-5 py-5">
      <h2 className="text-[13px] font-semibold text-critical">
        {variant === "review" ? t("review.projectUnavailable") : t(NOTICE_TITLES[variant])}
      </h2>
      <p className="mt-2 text-[12px] text-ink-muted">{reason}</p>
      {hint && <p className="mt-2 text-[12px] text-ink-muted">{hint}</p>}
    </div>
  );
}
