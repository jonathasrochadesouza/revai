"use client";

import { BackToDashboardLink } from "@/components/links";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
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

/**
 * Shown when the backend is unreachable or the prompts file is malformed.
 * Mirrors the Engine page: 422 means broken YAML the user can fix, anything
 * else means the process is not running.
 */
export function PromptsUnavailable({ reason, apiBaseUrl }: { reason: string; apiBaseUrl: string }) {
  const { t } = useUiText();
  return (
    <>
      <div className="mb-7">
        <p className="eyebrow mb-2">{t("settings.eyebrow")}</p>
        <h1 className="text-[26px] font-bold tracking-[-0.7px]">{t("settings.prompts.title")}</h1>
      </div>

      <Card>
        <CardHeader title={t("settings.prompts.unavailable")} icon={ALERT} aside={apiBaseUrl} />
        <CardBody>
          <div className="rounded-control border border-critical-line bg-critical-surface p-4">
            <p className="mb-3 text-[12.5px] leading-relaxed text-ink-muted">{reason}</p>
            <p className="mb-2 text-[12.5px] text-ink-muted">{t("settings.prompts.startBackendHint")}</p>
            <pre className="overflow-x-auto rounded-chip border border-line bg-paper px-3 py-2.5 text-[11.5px] leading-relaxed">
              {"cd platform/api\nuv sync --all-groups\nuv run revai-api"}
            </pre>
          </div>

          <BackToDashboardLink />
        </CardBody>
      </Card>
    </>
  );
}

const ALERT = (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    className="size-[15px] text-critical"
  >
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);
