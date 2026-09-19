/**
 * FindingCard — one review finding with severity, evidence and triage.
 *
 * Extracted from the review workspace so the finding contract has a single,
 * testable owner. The card is self-contained: expansion, patch copy and the
 * three status decisions for open findings all live here.
 */

"use client";

import { useState } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";
import type { Finding, Severity } from "@/lib/api";

const SEVERITY_STYLES: Record<Severity, string> = {
  critical: "border-critical-line bg-critical-surface text-critical",
  medium: "border-medium-line bg-medium-surface text-medium",
  low: "border-low-line bg-low-surface text-low",
};

export function FindingCard({
  finding,
  onStatus,
}: {
  finding: Finding;
  onStatus: (status: Finding["status"]) => void;
}) {
  const { t } = useUiText();
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const copyPatch = async () => {
    if (!finding.suggested_patch) return;
    await navigator.clipboard.writeText(finding.suggested_patch);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };
  return (
    <article className="px-4 py-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span
          className={`rounded-chip border px-2 py-0.5 text-[9.5px] font-semibold capitalize ${SEVERITY_STYLES[finding.severity]}`}
        >
          {t(`review.severity.${finding.severity}`)}
        </span>
        <span className="font-mono text-[10px] text-ink-subtle">
          {finding.file}:{finding.line_start}
        </span>
        <span className="text-[9.5px] font-semibold uppercase text-ink-subtle">{finding.source}</span>
        <span className="ml-auto text-[9.5px] font-semibold capitalize text-ink-subtle">{t(`review.finding.status.${finding.status}`)}</span>
      </div>
      <h5 className="text-[12.5px] font-semibold leading-snug">{finding.title}</h5>
      <p className="mt-1 text-[11.5px] leading-relaxed text-ink-muted">{finding.description}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => setExpanded((value) => !value)} className="text-[10.5px] font-semibold text-low hover:underline">
          {expanded ? t("review.finding.hideEvidence") : t("review.finding.whyThisMatters")}
        </button>
        <span className="text-[10.5px] text-ink-subtle">{t("review.finding.confidence", { percent: Math.round(finding.confidence * 100) })}</span>
        {finding.suggested_patch && <button type="button" onClick={() => void copyPatch()} className="text-[10.5px] font-semibold text-low hover:underline">{copied ? t("review.finding.patchCopied") : t("review.finding.copyPatch")}</button>}
      </div>
      {expanded && (
        <div className="mt-3 border-l-2 border-low-line bg-canvas px-3 py-2.5 text-[11px] leading-relaxed text-ink-muted">
          <p>{finding.rationale || t("review.finding.defaultRationale")}</p>
          {finding.suggested_patch && <pre className="mt-3 overflow-auto border border-line bg-paper p-2 font-mono text-[10px] text-ink">{finding.suggested_patch}</pre>}
        </div>
      )}
      {finding.status === "open" && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={() => onStatus("fixed")} className="border border-success-line px-2 py-1 text-[10.5px] font-semibold text-success hover:bg-success-surface">{t("review.finding.markFixed")}</button>
          <button type="button" onClick={() => onStatus("false_positive")} className="border border-line px-2 py-1 text-[10.5px] font-semibold text-ink-muted hover:bg-canvas">{t("review.finding.falsePositive")}</button>
          <button type="button" onClick={() => onStatus("dismissed")} className="border border-line px-2 py-1 text-[10.5px] font-semibold text-ink-muted hover:bg-canvas">{t("review.finding.dismiss")}</button>
        </div>
      )}
    </article>
  );
}
