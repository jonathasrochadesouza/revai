/**
 * Local SonarQube panel — Settings › Engine.
 *
 * Probes the backend for Docker/container/server state and drives the SSE
 * provisioning flow. The user only has to confirm Docker is running and, when
 * applicable, mark the WSL checkbox; server URL, project key and credentials
 * come from defaults and land in credentials.yaml once provisioned.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";
import { Loader } from "@/components/ui/loader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { api, type SonarStatusResponse, type SonarStreamEvent } from "@/lib/api";

interface SonarLocalPanelProps {
  wsl: boolean;
  onWslChange: (checked: boolean) => void;
}

export function SonarLocalPanel({ wsl, onWslChange }: SonarLocalPanelProps) {
  const { t } = useUiText();
  const [status, setStatus] = useState<SonarStatusResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [progressKey, setProgressKey] = useState<string | null>(null);
  const [failureKey, setFailureKey] = useState<string | null>(null);
  const [startedOnce, setStartedOnce] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  /**
   * Probe Docker/container/server state on mount and after each action.
   *
   * State is set from the promise callbacks — the effect subscribes to an
   * external system and reports back when it answers, the shape React's rules
   * allow (same pattern as ProviderPanel).
   */
  useEffect(() => {
    let cancelled = false;
    api.getSonarStatus().then(
      (data) => {
        if (!cancelled) setStatus(data);
      },
      () => {
        if (!cancelled) setStatus(null);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [startedOnce, busy]);

  useEffect(
    () => () => abortRef.current?.abort(),
    [],
  );

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.getSonarStatus());
    } catch {
      setStatus(null);
    }
  }, []);

  function onEvent(event: SonarStreamEvent) {
    setProgressKey(event.type);
    if (event.type === "failed") setFailureKey(event.error_key);
  }

  async function start() {
    setBusy(true);
    setFailureKey(null);
    setProgressKey("docker_checked");
    setStartedOnce(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await api.startSonar({ signal: controller.signal, onEvent });
    } catch (error) {
      const message = error instanceof Error ? error.message : null;
      if (!controller.signal.aborted && message && message.startsWith("sonarqube.")) {
        setFailureKey(message);
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
      await refresh();
    }
  }

  async function stop() {
    setBusy(true);
    try {
      setStatus(await api.stopSonar());
    } finally {
      setBusy(false);
    }
  }

  async function forgetToken() {
    setBusy(true);
    try {
      await api.deleteSonarCredentials();
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  const docker = status?.docker;
  const running = status?.container.running ?? false;
  const serverUp = status?.server.up ?? false;
  const provisioned = status?.provisioned ?? false;

  return (
    <div className="mt-3 rounded-control border border-line bg-canvas p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <b className="block text-[12.5px] font-medium">{t("engine.sonar.localTitle")}</b>
          <span className="text-[10.5px] text-ink-subtle">{t("engine.sonar.localDetail")}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {busy ? (
            <Loader variant="spinner" size="sm" />
          ) : (
            <>
              <Button variant="primary" onClick={() => void start()}>
                {t("engine.sonar.action.start")}
              </Button>
              {running && (
                <Button variant="secondary" onClick={() => void stop()}>
                  {t("engine.sonar.action.stop")}
                </Button>
              )}
            </>
          )}
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <Badge dot tone={docker?.running ? "success" : docker?.installed ? "medium" : "critical"}>
          {t("engine.sonar.docker")}
          {docker?.version ? ` ${docker.version}` : ""}
        </Badge>
        <Badge dot tone={running ? "success" : "low"}>
          {t("engine.sonar.container")}
        </Badge>
        <Badge dot tone={serverUp ? "success" : "critical"}>
          {t("engine.sonar.server")}
        </Badge>
        {provisioned && <Badge dot tone="success">{t("engine.sonar.token")}</Badge>}
      </div>

      {startedOnce && busy && progressKey && (
        <p className="mt-2 text-[11.5px] text-ink-muted">
          {t(`engine.sonar.progress.${progressKey}`)}
        </p>
      )}
      {failureKey && (
        <p className="mt-2 rounded-control border border-critical-line bg-critical-surface px-3 py-2 text-[12px] text-critical">
          {t(`engine.sonar.errors.${failureKey}`)}
        </p>
      )}

      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <Switch label={t("engine.sonar.wsl")} checked={wsl} onChange={onWslChange} />
          <span className="mt-0.5 block text-[10.5px] text-ink-subtle">
            {t("engine.sonar.wslHint")}
          </span>
        </div>
        {provisioned && !busy && (
          <button
            type="button"
            onClick={() => void forgetToken()}
            className="shrink-0 rounded-xs text-[10.5px] font-medium text-ink-subtle underline hover:text-critical"
          >
            <span className="numeric">{status?.token_masked}</span> · {t("engine.sonar.forgetToken")}
          </button>
        )}
      </div>
    </div>
  );
}
