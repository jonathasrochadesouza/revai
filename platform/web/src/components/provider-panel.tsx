/**
 * Detected providers.
 *
 * Deliberately a client component that fetches after mount, not part of the server
 * render: probing spawns three CLI subprocesses and, on this machine, `copilot`
 * alone takes over a second to start. Blocking the whole settings page on that
 * would make every navigation feel broken. The panel loads with the page and
 * fills in.
 *
 * The honesty rules this panel follows:
 *
 *   * `unknown` is shown as its own state, never rounded up to "ready". GitHub
 *     Copilot CLI ships no auth-status command and returns exit code 0 even for
 *     invalid input, so its auth state genuinely cannot be determined without
 *     spending a request.
 *   * `adapter_ready` remains distinct from installation and authentication, so a
 *     future recognised provider can still be listed without being selectable.
 *
 * Hosted APIs use zero-token model/key endpoints, while local agents use version
 * and sign-in probes. All eight adapters are therefore visible and testable from
 * one place without starting a paid review.
 */

"use client";

import { useEffect, useState } from "react";

import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { useUiText } from "@/components/ui-preference-bootstrap";
import {
  ApiError,
  api,
  isUsable,
  type HealthState,
  type ProviderHealth,
  type ProviderId,
  type ProvidersResponse,
} from "@/lib/api";
import { labelForProvider } from "@/lib/models";

/** Presentation for each health state, in one place so no card invents its own. */
const STATES: Record<HealthState, { labelKey: string; tone: BadgeTone }> = {
  ready: { labelKey: "engine.state.ready", tone: "success" },
  needs_auth: { labelKey: "engine.state.needs_auth", tone: "medium" },
  unknown: { labelKey: "engine.state.unknown", tone: "medium" },
  not_found: { labelKey: "engine.state.not_found", tone: "neutral" },
  error: { labelKey: "engine.state.error", tone: "critical" },
};

interface ProviderPanelProps {
  /** The provider currently selected in the form, highlighted in the list. */
  activeProviderId: ProviderId;
}

type Load =
  | { phase: "loading" }
  | { phase: "ready"; data: ProvidersResponse }
  | { phase: "error"; reason: string | null };

export function ProviderPanel({ activeProviderId }: ProviderPanelProps) {
  const { t } = useUiText();
  const [load, setLoad] = useState<Load>({ phase: "loading" });
  const [verifying, setVerifying] = useState<ProviderId | null>(null);
  const [scan, setScan] = useState(0);

  /**
   * Probe every provider whenever `scan` changes.
   *
   * State is set from the promise callbacks rather than after an `await` in the
   * effect body: the effect subscribes to an external system and reports back when
   * it answers, which is exactly the shape React's rules allow. `cancelled` guards
   * against a late response landing on an unmounted component, which would
   * otherwise leak a spinner-to-content flash if the user navigates away mid-probe.
   */
  useEffect(() => {
    let cancelled = false;

    api.getProviders().then(
      (data) => {
        if (!cancelled) {
          setLoad({ phase: "ready", data });
        }
      },
      (cause: unknown) => {
        if (!cancelled) {
          setLoad({
            phase: "error",
            reason: cause instanceof ApiError ? cause.message : null,
          });
        }
      },
    );

    return () => {
      cancelled = true;
    };
  }, [scan]);

  function rescan() {
    setLoad({ phase: "loading" });
    setScan((current) => current + 1);
  }

  /**
   * Re-probe one provider and splice the fresh result in.
   *
   * Only that provider's card changes — re-running the whole sweep would restart
   * every subprocess and blank the panel for a second, which reads as a bug.
   */
  async function verify(providerId: ProviderId) {
    setVerifying(providerId);
    try {
      const fresh = await api.verifyProvider(providerId);
      setLoad((current) =>
        current.phase === "ready"
          ? {
              phase: "ready",
              data: {
                ...current.data,
                providers: current.data.providers.map((p) =>
                  p.provider_id === providerId ? fresh : p,
                ),
                active_is_usable:
                  providerId === current.data.active_provider_id
                    ? isUsable(fresh)
                    : current.data.active_is_usable,
              },
            }
          : current,
      );
    } catch {
      // A failed verify is not a failed panel: the existing card stays, and the
      // user can try again. Blanking the list would lose the other results.
    } finally {
      setVerifying(null);
    }
  }

  return (
    <Card className="mb-3.5">
      <CardHeader
        title={t("engine.providerStatus")}
        icon={PLUG}
        aside={
          load.phase === "ready"
            ? t("engine.usableCount", {
                usable: load.data.providers.filter(isUsable).length,
                total: load.data.providers.length,
              })
            : undefined
        }
      />
      <CardBody>
        {load.phase === "loading" && <Spinner />}

        {load.phase === "error" && (
          <p className="rounded-control border border-critical-line bg-critical-surface px-3 py-2.5 text-[12.5px] text-critical">
            {load.reason ?? t("engine.couldNotReachApi")}
          </p>
        )}

        {load.phase === "ready" && (
          <>
            {load.data.providers.map((health) => (
              <ProviderRow
                key={health.provider_id}
                health={health}
                active={health.provider_id === activeProviderId}
                busy={verifying === health.provider_id}
                onVerify={() => void verify(health.provider_id)}
              />
            ))}

            <div className="mt-4 flex items-center gap-3 border-t border-line pt-3.5">
              <p className="text-[11.5px] leading-relaxed text-ink-subtle">
                {t("engine.probingNote")}
              </p>
              <Button
                variant="ghost"
                className="ml-auto shrink-0 px-3 py-1.5 text-[12px]"
                onClick={rescan}
              >
                {t("engine.rescan")}
              </Button>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}

function ProviderRow({
  health,
  active,
  busy,
  onVerify,
}: {
  health: ProviderHealth;
  active: boolean;
  busy: boolean;
  onVerify: () => void;
}) {
  const { t } = useUiText();
  const pill = STATES[health.state];

  return (
    <div className="flex items-start gap-3.5 border-b border-line py-3.5 first:pt-0 last:border-b-0 last:pb-0">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[13.5px] font-semibold">
            {labelForProvider(health.provider_id)}
          </p>
          {health.version && (
            <code className="numeric rounded-xs bg-canvas px-1.5 py-0.5 text-[11px] text-ink-muted">
              {health.version}
            </code>
          )}
          {active && <Badge tone="info">{t("engine.providerSelected")}</Badge>}
        </div>

        {health.detail && (
          <p className="mt-1 text-[12px] leading-relaxed text-ink-muted">
            {health.detail}
          </p>
        )}

        {/* Absolute path, because "not found" and "found the wrong one" look
            identical until you can see which file was resolved — `kiro` is the
            IDE launcher while `kiro-cli` is the agent. */}
        {health.executable && (
          <p className="mt-1 break-all font-mono text-[10.5px] text-ink-subtle">
            {health.executable}
          </p>
        )}

        {health.remediation && (
          <p className="mt-1.5 text-[11.5px] text-ink-muted">
            {t("engine.fix")}{" "}
            <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[11px] text-low">
              {health.remediation}
            </code>
          </p>
        )}

        {!health.adapter_ready && (
          <p className="mt-1.5 text-[11.5px] text-ink-subtle">
            {t("engine.adapterNotReady")}
          </p>
        )}
      </div>

      <div className="flex shrink-0 flex-col items-end gap-2">
        <Badge tone={pill.tone} dot={health.state === "ready"}>
          {t(pill.labelKey)}
        </Badge>
        <Button
          variant="ghost"
          className="px-3 py-1 text-[11.5px]"
          disabled={busy}
          onClick={onVerify}
        >
          {busy ? t("engine.testing") : t("engine.test")}
        </Button>
      </div>
    </div>
  );
}

/**
 * Shown for the whole time detection is running — never a fixed duration.
 *
 * A skeleton that guesses row heights was the wrong shape here: on a cold start
 * `copilot` alone can take over a second, so a static placeholder either sits still
 * long enough to look frozen, or gets swapped for "real" content that then jumps
 * around. A single centred spinner reads as "still working" for as long as that
 * actually takes, with no implied duration to be wrong about.
 */
function Spinner() {
  const { t } = useUiText();
  return (
    <div aria-busy className="flex flex-col items-center gap-3 py-9">
      <span
        aria-hidden
        className="size-7 animate-spin rounded-full border-2 border-line border-t-ink"
      />
      <p className="text-[12px] text-ink-subtle">
        {t("engine.probingHealth")}
      </p>
    </div>
  );
}

const PLUG = (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
    className="size-4"
    aria-hidden
  >
    <path d="M9 2v6" />
    <path d="M15 2v6" />
    <path d="M6 8h12v3a6 6 0 0 1-12 0Z" />
    <path d="M12 17v5" />
  </svg>
);
