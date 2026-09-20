"use client";

import { useUiText } from "@/components/ui-preference-bootstrap";

/**
 * Page title. Both storage paths are shown so a hand edit is discoverable:
 * skills in `skills.yaml`, prompts in `prompts.yaml`.
 */
export function SkillsPageHeader({
  skillsPath,
  promptsPath,
  locale,
}: {
  skillsPath: string;
  promptsPath: string;
  locale: "en-US" | "pt-BR";
}) {
  const { t } = useUiText();
  return (
    <div className="mb-7">
      <p className="eyebrow mb-2">{t("settings.eyebrow")}</p>
      <h1 className="mb-2.5 text-[26px] font-bold tracking-[-0.7px]">
        {t("settings.prompts.title")}
      </h1>
      <p className="max-w-[70ch] text-[14px] leading-relaxed text-ink-muted">
        {t("settings.prompts.subtitle.before")}{" "}
        <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[12.5px] text-low">
          {skillsPath}
        </code>{" "}
        {t("settings.prompts.subtitle.mid")}{" "}
        <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[12.5px] text-low">
          {promptsPath}
        </code>{" "}
        {t("settings.prompts.subtitle.after")}{" "}
        <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[12.5px] text-low">{locale}</code>
      </p>
    </div>
  );
}
