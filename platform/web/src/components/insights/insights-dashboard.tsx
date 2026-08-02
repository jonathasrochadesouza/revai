"use client";

import { AlertTriangle, Check, Clock3, DollarSign, SearchCode } from "lucide-react";
import { useRef, useState, useTransition } from "react";

import {
  api,
  type FindingCategory,
  type InsightRange,
  type InsightsResponse,
  type ReviewTrendPoint,
} from "@/lib/api";

const RANGES: InsightRange[] = ["7d", "30d", "90d", "all"];
const CATEGORY_LABELS: Record<FindingCategory, string> = {
  security: "Security",
  bug: "Correctness",
  performance: "Performance",
  maintainability: "Maintainability",
  style: "Style",
};

interface InsightsDashboardProps {
  initial: InsightsResponse;
  initialError?: string;
}

export function InsightsDashboard({ initial, initialError }: InsightsDashboardProps) {
  const [insights, setInsights] = useState(initial);
  const [selectedRange, setSelectedRange] = useState<InsightRange>(initial.range);
  const [error, setError] = useState(initialError);
  const [isPending, startTransition] = useTransition();
  const requestSequence = useRef(0);

  function selectRange(nextRange: InsightRange) {
    setSelectedRange(nextRange);
    setError(undefined);
    const sequence = ++requestSequence.current;
    startTransition(async () => {
      try {
        const next = await api.getInsights(nextRange);
        if (sequence === requestSequence.current) setInsights(next);
      } catch (cause) {
        if (sequence === requestSequence.current) {
          setError(cause instanceof Error ? cause.message : "Could not load insights.");
        }
      }
    });
  }

  const totals = insights.totals;
  const decided = totals.resolved_findings + totals.false_positives;
  const fixRate = decided + totals.open_findings > 0
    ? Math.round((totals.resolved_findings / (decided + totals.open_findings)) * 100)
    : 0;

  return (
    <main className="mx-auto w-full max-w-[1180px] px-5 pb-20 pt-10 sm:px-7">
      <section className="mb-9 flex flex-col justify-between gap-6 md:flex-row md:items-end">
        <div>
          <h1 className="max-w-[540px] text-[36px] font-bold leading-[1.05] tracking-[-1.6px] sm:text-[44px]">
            Code health, measured.
          </h1>
          <p className="mt-4 max-w-[620px] text-[14px] leading-relaxed text-ink-muted">
            Every review you run, aggregated from the YAML files on your disk. No
            cloud account, telemetry, or repository upload.
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-control border border-line bg-paper p-1" aria-label="Insight period">
          {RANGES.map((range) => (
            <button
              key={range}
              type="button"
              aria-pressed={selectedRange === range}
              disabled={isPending && selectedRange === range}
              onClick={() => selectRange(range)}
              className={`rounded-chip px-3 py-1.5 font-mono text-[10.5px] font-semibold uppercase transition-colors ${
                selectedRange === range
                  ? "bg-ink text-paper"
                  : "text-ink-muted hover:bg-canvas hover:text-ink"
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="mb-5 rounded-control border border-critical-line bg-critical-surface px-4 py-3 text-[12px] text-critical" role="alert">
          {error}
        </div>
      )}

      <section className={`surface mb-5 grid overflow-hidden sm:grid-cols-2 xl:grid-cols-4 ${isPending ? "opacity-70" : ""}`} aria-busy={isPending}>
        <Kpi icon={<SearchCode />} label="Reviews run" value={formatNumber(totals.reviews)} detail={`${totals.completed_reviews} completed`} />
        <Kpi icon={<AlertTriangle />} label="Issues caught" value={formatNumber(totals.findings)} detail={`${totals.open_critical} critical open`} />
        <Kpi icon={<DollarSign />} label="Total spend" value={formatCurrency(totals.total_cost_usd)} detail="Across selected reviews" />
        <Kpi icon={<Clock3 />} label="Median duration" value={formatDuration(totals.median_duration_ms)} detail="Per review" />
      </section>

      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1.7fr)_minmax(280px,0.8fr)]">
        <section className="surface min-w-0 overflow-hidden">
          <PanelHeader title="Findings over time" detail="Latest 12 reviews" />
          <TrendChart points={insights.trend} />
        </section>

        <section className="surface overflow-hidden">
          <PanelHeader title="By category" detail={`${formatNumber(totals.findings)} total`} />
          <CategoryBreakdown categories={insights.categories} total={totals.findings} />
        </section>
      </div>

      <section className="surface mb-5 grid gap-8 px-6 py-6 lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <h2 className="text-[18px] font-semibold tracking-[-0.3px]">Technical debt snapshot</h2>
          <p className="mt-2 max-w-[680px] text-[13px] leading-relaxed text-ink-muted">
            Current health uses each repository&apos;s latest review in the selected period.
            A score of 100 means that review has no unresolved findings.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-6 sm:gap-10">
          <DebtMetric value={totals.open_critical} label="Open critical" tone="critical" />
          <DebtMetric value={totals.resolved_findings} label="Resolved" tone="success" />
          <DebtMetric value={`${fixRate}%`} label="Fix rate" tone="low" />
        </div>
      </section>

      <section className="surface overflow-hidden">
        <PanelHeader title="Repository breakdown" detail={`${insights.projects.length} tracked`} />
        <RepositoryTable projects={insights.projects} />
      </section>
    </main>
  );
}

function Kpi({ icon, label, value, detail }: { icon: React.ReactElement; label: string; value: string; detail: string }) {
  return (
    <article className="border-b border-line px-5 py-5 last:border-b-0 sm:odd:border-r sm:[&:nth-last-child(-n+2)]:border-b-0 xl:border-b-0 xl:border-r xl:last:border-r-0">
      <div className="mb-4 flex items-center justify-between text-ink-subtle">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em]">{label}</span>
        <span className="[&>svg]:size-4 [&>svg]:stroke-[1.7]">{icon}</span>
      </div>
      <p className="numeric text-[26px] font-semibold tracking-[-1px]">{value}</p>
      <p className="mt-1 text-[10.5px] text-ink-subtle">{detail}</p>
    </article>
  );
}

function PanelHeader({ title, detail }: { title: string; detail: string }) {
  return (
    <header className="flex items-center justify-between border-b border-line px-5 py-3.5">
      <h2 className="text-[12.5px] font-semibold">{title}</h2>
      <span className="font-mono text-[9.5px] uppercase text-ink-subtle">{detail}</span>
    </header>
  );
}

function TrendChart({ points }: { points: ReviewTrendPoint[] }) {
  if (points.length === 0) {
    return <EmptyState message="Run a review to start measuring findings over time." />;
  }
  const maxTotal = Math.max(1, ...points.map((point) => point.critical + point.medium + point.low));
  return (
    <div className="px-5 pb-5 pt-7">
      <div className="flex h-[210px] items-end gap-2 border-b border-line sm:gap-3">
        {points.map((point, index) => (
          <div key={point.review_id} className="flex h-full min-w-0 flex-1 flex-col justify-end" title={`${point.project_name}: ${point.critical + point.medium + point.low} open findings`}>
            <div className="flex min-h-px w-full flex-col justify-end overflow-hidden rounded-t-xs">
              <ChartSegment value={point.low} max={maxTotal} tone="bg-low" />
              <ChartSegment value={point.medium} max={maxTotal} tone="bg-medium" />
              <ChartSegment value={point.critical} max={maxTotal} tone="bg-critical" />
            </div>
            <span className="mt-2 truncate text-center font-mono text-[8.5px] text-ink-subtle">R{index + 1}</span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-4 text-[10px] text-ink-muted">
        <Legend tone="bg-critical" label="Critical" />
        <Legend tone="bg-medium" label="Medium" />
        <Legend tone="bg-low" label="Low" />
      </div>
    </div>
  );
}

function ChartSegment({ value, max, tone }: { value: number; max: number; tone: string }) {
  if (value === 0) return null;
  return <span className={`${tone} block min-h-[3px] w-full`} style={{ height: `${Math.max(3, (value / max) * 170)}px` }} />;
}

function Legend({ tone, label }: { tone: string; label: string }) {
  return <span className="flex items-center gap-1.5"><i className={`size-2 rounded-xs ${tone}`} />{label}</span>;
}

function CategoryBreakdown({ categories, total }: { categories: InsightsResponse["categories"]; total: number }) {
  return (
    <div className="space-y-4 px-5 py-5">
      {(Object.entries(CATEGORY_LABELS) as [FindingCategory, string][]).map(([category, label]) => {
        const value = categories[category];
        const percent = total > 0 ? Math.round((value / total) * 100) : 0;
        return (
          <div key={category}>
            <div className="mb-1.5 flex items-center justify-between text-[10.5px]">
              <span className="text-ink-muted">{label}</span>
              <span className="font-mono text-ink-subtle">{value} · {percent}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-xs bg-canvas">
              <span className="block h-full bg-ink" style={{ width: `${percent}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DebtMetric({ value, label, tone }: { value: string | number; label: string; tone: "critical" | "success" | "low" }) {
  const colors = { critical: "text-critical", success: "text-success", low: "text-low" };
  return <div><b className={`numeric block text-[22px] ${colors[tone]}`}>{value}</b><span className="text-[9px] uppercase text-ink-subtle">{label}</span></div>;
}

function RepositoryTable({ projects }: { projects: InsightsResponse["projects"] }) {
  if (projects.length === 0) return <EmptyState message="Open a repository to add it to code-health insights." />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left">
        <thead className="bg-sunken text-[9.5px] font-semibold uppercase tracking-[0.06em] text-ink-subtle">
          <tr><th className="px-5 py-3">Repository</th><th className="px-4 py-3">Reviews</th><th className="px-4 py-3">Open</th><th className="px-4 py-3">Critical</th><th className="px-4 py-3">Health</th><th className="px-5 py-3">Change</th></tr>
        </thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.project_id} className="border-t border-line text-[11.5px]">
              <td className="px-5 py-3.5"><div className="font-semibold">{project.name}</div><div className="mt-0.5 font-mono text-[9.5px] text-ink-subtle">{project.languages.join(" · ") || "language unknown"}</div></td>
              <td className="px-4 py-3.5 font-mono">{project.reviews}</td>
              <td className="px-4 py-3.5 font-mono">{project.open_findings}</td>
              <td className={`px-4 py-3.5 font-mono ${project.open_critical > 0 ? "text-critical" : "text-ink"}`}>{project.open_critical}</td>
              <td className="px-4 py-3.5"><HealthScore score={project.health_score} /></td>
              <td className="px-5 py-3.5 font-mono"><HealthChange value={project.health_change} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HealthScore({ score }: { score: number }) {
  const tone = score >= 85 ? "border-success-line bg-success-surface text-success" : score >= 60 ? "border-medium-line bg-medium-surface text-medium" : "border-critical-line bg-critical-surface text-critical";
  return <span className={`inline-flex min-w-10 justify-center rounded-chip border px-2 py-1 font-mono text-[10px] font-semibold ${tone}`}>{score}</span>;
}

function HealthChange({ value }: { value: number | null }) {
  if (value === null) return <span className="text-ink-subtle">new</span>;
  if (value === 0) return <span className="text-ink-subtle">0</span>;
  return <span className={value > 0 ? "text-success" : "text-critical"}>{value > 0 ? "+" : ""}{value}</span>;
}

function EmptyState({ message }: { message: string }) {
  return <div className="grid min-h-[240px] place-items-center px-6 text-center"><div><Check className="mx-auto mb-3 size-6 text-success" /><p className="text-[12px] text-ink-muted">{message}</p></div></div>;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(value);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatDuration(milliseconds: number): string {
  if (milliseconds <= 0) return "—";
  const seconds = Math.round(milliseconds / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
