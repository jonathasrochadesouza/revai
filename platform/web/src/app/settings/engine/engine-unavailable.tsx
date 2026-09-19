"use client";

import { BackToDashboardLink } from "@/components/links";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
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
/**
 * Shown when the backend is unreachable or its config file is malformed.
 *
 * The distinction matters: a 422 means the YAML is broken and the message names
 * the field, whereas a network failure means the process is not running.
 */
export function EngineUnavailable({ reason, apiBaseUrl }: { reason: string; apiBaseUrl: string }) {
  const { t } = useUiText();
  return (
    <>
      <div className="mb-7">
        <p className="eyebrow mb-2">{t("settings.eyebrow")}</p>
        <h1 className="text-[26px] font-bold tracking-[-0.7px]">{t("settings.engine.title")}</h1>
      </div>

      <Card>
        <CardHeader title={t("settings.engine.configurationUnavailable")} icon={ALERT} aside={apiBaseUrl} />
        <CardBody>
          <div className="rounded-control border border-critical-line bg-critical-surface p-4">
            <p className="mb-2 text-[13.5px] font-semibold text-critical">
              {t("settings.engine.noConfigReturned")}
            </p>
            <p className="mb-3 text-[12.5px] leading-relaxed text-ink-muted">{reason}</p>
            <p className="mb-2 text-[12.5px] text-ink-muted">
              {t("settings.engine.startBackendHint")}
            </p>
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
  </svg>
);
