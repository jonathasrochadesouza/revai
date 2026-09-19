/**
 * Review agent panel — Settings › Engine.
 *
 * Installs the RevAI reviewer into a project: writes a managed block into the
 * project's AGENTS.md and ships the standalone HTML report template. Every
 * action is explicit — preview first, apply on click — and the sample report
 * iframe shows exactly what an agent review will look like.
 */

"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/field";
import { useUiText } from "@/components/ui-preference-bootstrap";
import {
  api,
  type AgentApplyResult,
  type AgentPreview,
  type Project,
} from "@/lib/api";
import { useApiErrorText } from "@/lib/use-api-error-text";

export function AgentPanel() {
  const { t } = useUiText();
  const errorText = useApiErrorText();
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [preview, setPreview] = useState<AgentPreview | null>(null);
  const [result, setResult] = useState<AgentApplyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDemo, setShowDemo] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getProjects()
      .then((response) => {
        if (cancelled) return;
        const active = response.projects.filter((project) => !project.archived);
        setProjects(active);
        setProjectId((current) => current || active[0]?.id || "");
      })
      .catch(() => {
        if (!cancelled) setProjects([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const previewAgent = useCallback(async (id: string) => {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      setPreview(await api.getAgentPreview(id));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }, [errorText]);

  const applyAgent = useCallback(async () => {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    try {
      const applied = await api.applyAgent(projectId);
      setResult(applied);
      setPreview(await api.getAgentPreview(projectId));
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }, [projectId, errorText]);

  return (
    <section className="mt-7">
      <Card>
        <CardHeader
          title={t("agent.cardTitle")}
          aside={<Badge tone="low">AGENTS.md</Badge>}
        />
        <CardBody>
          <p className="max-w-[640px] text-[12.5px] text-ink-muted">{t("agent.intro")}</p>

          <div className="mt-3 flex flex-wrap items-end gap-3">
            <label className="min-w-[220px] grow-0">
              <span className="mb-1 block text-[10.5px] font-medium uppercase tracking-wide text-ink-subtle">
                {t("agent.project")}
              </span>
              <Select
                value={projectId}
                onChange={(event) => {
                  setProjectId(event.target.value);
                  setPreview(null);
                  setResult(null);
                }}
              >
                {projects.length === 0 && <option value="">—</option>}
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </Select>
            </label>
            <Button
              variant="secondary"
              disabled={!projectId || busy}
              onClick={() => void previewAgent(projectId)}
            >
              {t("agent.preview")}
            </Button>
            <Button
              variant="primary"
              disabled={!projectId || busy}
              onClick={() => void applyAgent()}
            >
              {busy ? t("agent.applying") : t("agent.apply")}
            </Button>
          </div>

          {error && (
            <p className="mt-3 rounded-control border border-critical-line bg-critical-surface px-3 py-2 text-[12px] text-critical">
              {error}
            </p>
          )}

          {preview && (
            <div className="mt-4">
              <div className="flex flex-wrap items-center gap-2">
                <b className="text-[12.5px] font-medium">{t("agent.previewTitle")}</b>
                <code className="numeric text-[11px] text-ink-subtle">{preview.agents_md_path}</code>
                <Badge dot tone={preview.agents_md_exists ? "medium" : "success"}>
                  {preview.agents_md_exists ? t("agent.existingFile") : t("agent.newFile")}
                </Badge>
              </div>
              <pre className="mt-2 max-h-[320px] overflow-auto rounded-control border border-line bg-canvas p-3 text-[11px] leading-relaxed whitespace-pre-wrap">
                {preview.agents_md}
              </pre>
              <p className="mt-1.5 text-[11px] text-ink-subtle">
                {t("agent.engine")}: <span className="numeric">{preview.engine}</span>
              </p>
            </div>
          )}

          {result && (
            <p className="mt-3 rounded-control border border-success-line bg-success-surface px-3 py-2 text-[12px] text-success">
              {t("agent.applied")} <code className="numeric">{result.agents_md}</code>
            </p>
          )}

          <div className="mt-4 border-t border-line pt-3">
            <Button variant="ghost" onClick={() => setShowDemo((current) => !current)}>
              {showDemo ? "− " : "+ "}
              {t("agent.reportDemo")}
            </Button>
            {showDemo && (
              <iframe
                title={t("agent.reportDemo")}
                src={api.agentReportDemoUrl()}
                className="mt-3 h-[560px] w-full rounded-control border border-line bg-white"
              />
            )}
          </div>
        </CardBody>
      </Card>
    </section>
  );
}
