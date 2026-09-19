"use client";

import { Archive, Download, FileCode2, FileJson2, FileText, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";
import { api, reviewExportUrl, type DataSummary, type Review } from "@/lib/api";

export interface ReviewExportRow {
  projectName: string;
  review: Review;
}

export function ExportDataPanel({ summary, reviews }: { summary: DataSummary; reviews: ReviewExportRow[] }) {
  const { t } = useUiText();
  const [archiveState, setArchiveState] = useState<"idle" | "working" | "done">("idle");
  const [error, setError] = useState<string>();

  async function downloadArchive() {
    setArchiveState("working");
    setError(undefined);
    try {
      const blob = await api.exportAllData();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "revai-data.zip";
      anchor.click();
      URL.revokeObjectURL(url);
      setArchiveState("done");
    } catch (cause) {
      setArchiveState("idle");
      setError(cause instanceof Error ? cause.message : t("data.exportError"));
    }
  }

  return (
    <div className="space-y-5">
      <section className="surface overflow-hidden">
        <header className="flex items-center gap-2 border-b border-line px-5 py-4">
          <Archive className="size-4 text-ink-muted" strokeWidth={1.8} />
          <h2 className="text-[13px] font-semibold">{t("data.exportCard")}</h2>
        </header>
        <div className="divide-y divide-line">
          <DataRow title={t("data.reviewHistory")} detail={`${t("data.reviewsCount", { count: summary.reviews })} · ${formatBytes(summary.storage_bytes)}`} aside={<code className="text-[10px] text-ink-subtle">{summary.reviews_dir}</code>} />
          <DataRow title={t("data.exportEverything")} detail={t("data.exportEverythingDetail")}>
            <button type="button" onClick={downloadArchive} disabled={archiveState === "working"} className="inline-flex items-center gap-2 rounded-control border border-line-strong px-3 py-2 text-[11px] font-medium hover:bg-canvas disabled:opacity-50">
              <Download className="size-3.5" />
              {archiveState === "working" ? t("data.buildingArchive") : archiveState === "done" ? t("data.exported") : t("data.exportZip")}
            </button>
          </DataRow>
          <DataRow title={t("data.credentialSafety")} detail={t("data.credentialSafetyDetail")} aside={<span className="inline-flex items-center gap-1.5 text-[10.5px] font-semibold text-success"><ShieldCheck className="size-3.5" />{t("data.excluded")}</span>} />
        </div>
      </section>

      {error && <p role="alert" className="rounded-control border border-critical-line bg-critical-surface px-4 py-3 text-[12px] text-critical">{error}</p>}

      <section className="surface overflow-hidden">
        <header className="border-b border-line px-5 py-4">
          <h2 className="text-[13px] font-semibold">{t("data.recentExports")}</h2>
          <p className="mt-1 text-[11px] text-ink-subtle">{t("data.recentExportsDetail")}</p>
        </header>
        {reviews.length === 0 ? (
          <div className="px-5 py-10 text-center text-[12px] text-ink-muted">{t("data.runReviewFirst")}</div>
        ) : (
          <div className="divide-y divide-line">
            {reviews.map(({ projectName, review }) => (
              <article key={review.id} className="flex flex-col gap-4 px-5 py-4 lg:flex-row lg:items-center">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="truncate text-[12.5px] font-semibold">{projectName === "Unknown project" ? t("data.unknownProject") : projectName}</h3>
                    <span className="rounded-chip border border-line px-2 py-0.5 text-[9px] uppercase text-ink-subtle">{t(`status.${review.status}`)}</span>
                  </div>
                  <p className="mt-1 truncate font-mono text-[10px] text-ink-subtle">{review.head_branch ?? t("data.workingTree")} · {new Date(review.created_at).toLocaleString()} · {t("data.findingsCount", { count: review.findings.length })}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <ExportLink href={reviewExportUrl(review.id, "json")} icon={<FileJson2 />} label="JSON" />
                  <ExportLink href={reviewExportUrl(review.id, "md")} icon={<FileText />} label="Markdown" />
                  <ExportLink href={reviewExportUrl(review.id, "sarif")} icon={<FileCode2 />} label="SARIF" />
                  <ExportLink href={reviewExportUrl(review.id, "html")} icon={<FileCode2 />} label="HTML" primary />
                  <ExportLink href={reviewExportUrl(review.id, "json", true)} icon={<FileJson2 />} label={t("data.legacy")} />
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function DataRow({ title, detail, aside, children }: { title: string; detail: string; aside?: React.ReactNode; children?: React.ReactNode }) {
  return <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center"><div className="min-w-0 flex-1"><h3 className="text-[12px] font-semibold">{title}</h3><p className="mt-1 text-[10.5px] text-ink-subtle">{detail}</p></div>{aside ?? children}</div>;
}

function ExportLink({ href, icon, label, primary = false }: { href: string; icon: React.ReactElement; label: string; primary?: boolean }) {
  return <a href={href} className={`inline-flex items-center gap-1.5 rounded-control border px-2.5 py-1.5 text-[10.5px] font-medium ${primary ? "border-ink bg-ink text-paper hover:bg-ink-muted" : "border-line-strong bg-paper text-ink-muted hover:bg-canvas hover:text-ink"}`}><span className="[&>svg]:size-3.5">{icon}</span>{label}</a>;
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 ** 2).toFixed(1)} MB`;
}
