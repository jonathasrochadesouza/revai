"use client";

import { useUiText } from "@/components/ui-preference-bootstrap";
export function EnginePageHeader({ configPath }: { configPath: string }) {
  const { t } = useUiText();
  return (
    <div className="mb-7">
      <p className="eyebrow mb-2">{t("settings.eyebrow")}</p>
      <h1 className="mb-2.5 text-[26px] font-bold tracking-[-0.7px]">
        {t("settings.engine.title")}
      </h1>
      <p className="max-w-[70ch] text-[14px] leading-relaxed text-ink-muted">
        {t("settings.engine.subtitle.before")}{" "}
        <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[12.5px] text-low">
          {configPath}
        </code>{" "}
        {t("settings.engine.subtitle.after")}
      </p>
    </div>
  );
}
