/**
 * Settings › API & AI — the diagnosis screen.
 *
 * The division of labour with Settings › Engine is deliberate: *this* screen answers
 * "is it working right now, and what do I do about it", while Engine answers "how do
 * I want it configured". Both read provider state from the same backend probe, so
 * they cannot contradict each other.
 *
 * A client component reading the shared connection store rather than a server fetch:
 * the store has usually already probed by the time this route renders, the re-check
 * button needs the live payload, and an unreachable backend must render the recovery
 * screen instead of a half-filled panel.
 */

"use client";

import Link from "next/link";

import { BackendUnreachable } from "@/components/backend-unreachable";
import { useConnection } from "@/components/connection-provider";
import { useUiText } from "@/components/ui-preference-bootstrap";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardRow } from "@/components/ui/card";
import { Loader } from "@/components/ui/loader";
import { API_BASE_URL, type HealthState } from "@/lib/api";
import { labelForProvider } from "@/lib/models";

/** Same state presentation as the engine provider panel, so the two never diverge. */
const STATES: Record<HealthState, { labelKey: string; tone: BadgeTone }> = {
  ready: { labelKey: "engine.state.ready", tone: "success" },
  needs_auth: { labelKey: "engine.state.needs_auth", tone: "medium" },
  unknown: { labelKey: "engine.state.unknown", tone: "medium" },
  not_found: { labelKey: "engine.state.not_found", tone: "neutral" },
  error: { labelKey: "engine.state.error", tone: "critical" },
};

export const RUN_BACKEND_DOC =
  (process.env.NEXT_PUBLIC_DOCS_URL ?? "http://127.0.0.1:3001") + "/run-the-backend";

export function ConnectionPanels() {
  const { t } = useUiText();
  const { phase, status, unreachableReason, refreshing, refresh } = useConnection();

  if (phase === "probing") {
    return (
      <div aria-busy className="flex flex-col items-center gap-3 py-12">
        <Loader variant="spinner" />
        <p className="text-[12px] text-ink-subtle">{t("connection.checking")}</p>
      </div>
    );
  }

  if (!status) {
    // The recovery screen owns this case: compose commands, the copyable
    // troubleshooting prompt and a retry, all already specified and built.
    return (
      <>
        <BackendUnreachable reason={unreachableReason ?? ""} apiBaseUrl={API_BASE_URL} />
        <p className="mt-4 text-[12.5px] text-ink-muted">
          <a
            href={RUN_BACKEND_DOC}
            target="_blank"
            rel="noopener noreferrer"
            className="text-low hover:underline"
          >
            {t("connection.api.howToStart")}
          </a>
        </p>
      </>
    );
  }

  const ai = status.ai;
  const activeState = STATES[ai.active_state];
  const checkedAt = new Date(status.checked_at).toLocaleTimeString();

  return (
    <>
      <div className="mb-3.5 flex flex-wrap items-center gap-3">
        <p className="numeric text-[11.5px] text-ink-subtle">
          {t("connection.checkedAt", { time: checkedAt })}
        </p>
        <Button
          variant="ghost"
          className="ml-auto px-3 py-1.5 text-[12px]"
          disabled={refreshing}
          onClick={() => void refresh()}
        >
          {refreshing ? t("connection.rechecking") : t("connection.recheck")}
        </Button>
      </div>

      <Card className="mb-3.5">
        <CardHeader
          title={t("connection.api.title")}
          aside={<Badge tone="success" dot>{t("common.apiConnected")}</Badge>}
        />
        <CardBody>
          <CardRow label={t("connection.api.address")}>
            <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[11.5px] text-low">
              {API_BASE_URL}
            </code>
          </CardRow>
          <CardRow label={t("connection.api.version")}>
            <span className="numeric text-[12.5px] text-ink-muted">{status.api.version}</span>
          </CardRow>
          <CardRow label={t("connection.api.environment")}>
            <span className="text-[12.5px] text-ink-muted">{status.api.environment}</span>
          </CardRow>
          <div className="mt-4 border-t border-line pt-3.5">
            <a
              href={RUN_BACKEND_DOC}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[12px] font-medium text-low hover:underline"
            >
              {t("connection.api.howToStart")}
            </a>
          </div>
        </CardBody>
      </Card>

      <Card className="mb-3.5">
        <CardHeader
          title={t("connection.ai.title")}
          aside={t("connection.ai.scoreboard", {
            ready: ai.ready_provider_ids.length,
            total: ai.total,
          })}
        />
        <CardBody>
          <CardRow
            label={t("connection.ai.activeProvider")}
            hint={labelForProvider(ai.active_provider_id)}
          >
            <Badge tone={activeState.tone} dot={ai.active_state === "ready"}>
              {t(activeState.labelKey)}
            </Badge>
          </CardRow>

          {ai.active_detail && (
            <p className="mt-3 text-[12px] leading-relaxed text-ink-muted">{ai.active_detail}</p>
          )}

          {/* Verbatim, monospaced: a remediation the user retypes must match exactly. */}
          {ai.active_remediation && (
            <p className="mt-1.5 text-[11.5px] text-ink-muted">
              {t("engine.fix")}{" "}
              <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[11px] text-low">
                {ai.active_remediation}
              </code>
            </p>
          )}

          <p className="mt-3 text-[11.5px] text-ink-subtle">
            {ai.ready_provider_ids.length > 0
              ? t("connection.ai.readyList", {
                  providers: ai.ready_provider_ids.map(labelForProvider).join(", "),
                })
              : t("connection.ai.noneReady")}
          </p>
          {ai.unknown_provider_ids.length > 0 && (
            <p className="mt-1 text-[11.5px] text-ink-subtle">
              {t("connection.ai.unknownList", {
                providers: ai.unknown_provider_ids.map(labelForProvider).join(", "),
              })}
            </p>
          )}

          <div className="mt-4 border-t border-line pt-3.5">
            <Link
              href="/settings/engine"
              className="inline-flex rounded-control border border-line-strong px-3 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink"
            >
              {t("connection.ai.configure")}
            </Link>
          </div>
        </CardBody>
      </Card>
    </>
  );
}
