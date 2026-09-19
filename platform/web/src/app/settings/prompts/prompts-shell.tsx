"use client";

import { useUiText } from "@/components/ui-preference-bootstrap";

/** Page title. The path is shown like the Engine page so the file is discoverable. */
export function PromptsPageHeader({ path, locale }: { path: string; locale: "en-US" | "pt-BR" }) {
  const { t } = useUiText();
  return (
    <div className="mb-7">
      <p className="eyebrow mb-2">{t("settings.eyebrow")}</p>
      <h1 className="mb-2.5 text-[26px] font-bold tracking-[-0.7px]">
        {t("settings.prompts.title")}
      </h1>
      <p className="max-w-[70ch] text-[14px] leading-relaxed text-ink-muted">
        {t("settings.prompts.subtitle.before")}{" "}
        <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[12.5px] text-low">{path}</code>{" "}
        {t("settings.prompts.subtitle.after")}{" "}
        <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[12.5px] text-low">{locale}</code>
      </p>
    </div>
  );
}
