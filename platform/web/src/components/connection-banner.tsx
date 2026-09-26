/**
 * Connection warning banner.
 *
 * A single small row directly under the primary navigation, inside the sticky
 * header, in the amber `medium` tone the design system already uses for warnings.
 *
 * Four rules it obeys, all specified:
 *
 *  * **Nothing before the first answer, nothing when healthy.** No placeholder, no
 *    skeleton — the page must not shift after load.
 *  * **One banner at a time**, with an unreachable backend outranking everything
 *    else: when the API is down the AI state is indeterminable, so claiming a
 *    provider problem as well would be inventing information.
 *  * **`role="status"` with `aria-live="polite"`**, not `alert`: this is a
 *    background condition, not an interruption of what the user is doing.
 *  * **Suppressed on the connection screen**, where the full diagnosis already is.
 */

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useConnection } from "@/components/connection-provider";
import { useUiText } from "@/components/ui-preference-bootstrap";
import type { ProblemKind } from "@/lib/connection-store";
import type { TranslateParams } from "@/lib/i18n";
import { labelForProvider } from "@/lib/models";
import type { StatusResponse } from "@/lib/api";

export const CONNECTION_HREF = "/settings/connection";

const MESSAGES: Record<ProblemKind, string> = {
  api_down: "connection.banner.apiDown",
  ai_active_broken: "connection.banner.aiActiveBroken",
  ai_none_ready: "connection.banner.aiNoneReady",
  ai_unknown: "connection.banner.aiUnknown",
};

/** Provider names for the two messages that name one. */
function params(
  problem: ProblemKind,
  status: StatusResponse | null,
): TranslateParams | undefined {
  if (!status) return undefined;
  const provider = labelForProvider(status.ai.active_provider_id);
  if (problem === "ai_unknown") return { provider };
  if (problem === "ai_active_broken") {
    const ready = status.ai.ready_provider_ids[0];
    return { provider, ready: ready ? labelForProvider(ready) : provider };
  }
  return undefined;
}

export function ConnectionBanner() {
  const { t } = useUiText();
  const { phase, problem, status, dismiss } = useConnection();
  const pathname = usePathname();

  if (phase === "probing" || problem === null) return null;
  if (pathname === CONNECTION_HREF) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex w-full items-center gap-2.5 border-t border-medium-line bg-medium-surface px-4 py-1 text-medium sm:px-7"
    >
      <svg
        aria-hidden
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="size-3.5 shrink-0"
      >
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>

      <p className="min-w-0 flex-1 truncate text-[11.5px] font-medium">
        {t(MESSAGES[problem], params(problem, status))}
      </p>

      <Link
        href={CONNECTION_HREF}
        className="shrink-0 rounded-xs text-[11.5px] font-semibold underline decoration-medium-line underline-offset-2 hover:decoration-current"
      >
        {t("connection.banner.action")}
      </Link>

      <button
        type="button"
        onClick={dismiss}
        aria-label={t("connection.banner.dismiss")}
        className="shrink-0 rounded-xs p-0.5 opacity-70 transition-opacity hover:opacity-100"
      >
        <svg
          aria-hidden
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2.2}
          strokeLinecap="round"
          className="size-3"
        >
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
}
