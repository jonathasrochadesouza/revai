/**
 * Settings "backend unreachable" recovery screen.
 *
 * Shared by every settings page whose server component could not load its
 * data. Beyond the copy and the two compose commands, it offers an AI
 * troubleshooting prompt: built by a pure function, copied straight to the
 * clipboard and never rendered into the DOM — its audience is the user's
 * coding agent, so it stays English regardless of the interface locale.
 */

"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";

export function buildTroubleshootingPrompt(reason: string): string {
  return [
    "The RevAI Platform web app cannot reach its local backend API.",
    `Technical detail: ${reason}`,
    "",
    "Troubleshooting steps:",
    "1. Check whether the Docker Compose service `api` is running: `docker compose ps`.",
    "2. If it is not, start it: `docker compose up -d`.",
    "3. Verify the API answers on http://127.0.0.1:8799/api/health.",
    "4. If it still fails, inspect the logs: `docker compose logs api --tail=100`.",
    "",
    "Diagnose why the RevAI api service on port 8799 is not reachable and propose the fix.",
  ].join("\n");
}

const COMPOSE_COMMANDS = ["docker compose ps", "docker compose logs api --tail=100"];

export function BackendUnreachable({ reason, apiBaseUrl }: { reason: string; apiBaseUrl: string }) {
  const { t } = useUiText();
  const router = useRouter();
  const [copied, setCopied] = useState(false);

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(buildTroubleshootingPrompt(reason));
      setCopied(true);
      // Transient confirmation on the button itself, 1.5 s, matching the
      // patch-copy pattern used in the review workspace.
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be denied; staying silent is better than a
      // broken-looking second error inside an error screen.
    }
  }

  return (
    <>
      <div className="mb-7">
        <p className="eyebrow mb-2">{t("unreachable.eyebrow")}</p>
        <h1 className="text-[26px] font-bold tracking-[-0.7px]">{t("unreachable.title")}</h1>
      </div>

      <Card>
        <CardHeader title={t("unreachable.cardTitle")} icon={UNPLUG} aside={apiBaseUrl} />
        <CardBody>
          <div className="rounded-control border border-critical-line bg-critical-surface p-4">
            <p className="mb-2 text-[13.5px] font-semibold text-critical">
              {t("unreachable.heading")}
            </p>
            <p className="mb-3 text-[12.5px] leading-relaxed text-ink-muted">
              {t("unreachable.body.before")}{" "}
              <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[12.5px] text-low">
                {apiBaseUrl}
              </code>{" "}
              {t("unreachable.body.after")}
            </p>
            <pre className="mb-3 overflow-x-auto rounded-chip border border-line bg-paper px-3 py-2.5 font-mono text-[11.5px] leading-relaxed">
              {COMPOSE_COMMANDS.join("\n")}
            </pre>
            <p className="truncate font-mono text-[11px] text-ink-subtle" title={reason}>
              {reason}
            </p>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2.5">
            <Button variant="primary" onClick={() => void copyPrompt()}>
              {copied ? t("unreachable.copied") : t("unreachable.copyPrompt")}
            </Button>
            <Button onClick={() => router.refresh()}>{t("unreachable.tryAgain")}</Button>
          </div>
        </CardBody>
      </Card>
    </>
  );
}

const UNPLUG = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="size-[15px] text-critical">
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);
