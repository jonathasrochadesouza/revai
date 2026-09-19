import { DataLink } from "@/components/links";
import { InsightsDashboard } from "@/components/insights/insights-dashboard";
import { TopBar } from "@/components/top-bar";
import { api, type InsightsResponse } from "@/lib/api";

export const metadata = {
  title: "Insights — RevAI",
};

const EMPTY_INSIGHTS: InsightsResponse = {
  range: "30d",
  generated_at: new Date(0).toISOString(),
  totals: {
    reviews: 0,
    completed_reviews: 0,
    findings: 0,
    open_findings: 0,
    open_critical: 0,
    resolved_findings: 0,
    false_positives: 0,
    total_cost_usd: 0,
    median_duration_ms: 0,
  },
  categories: { security: 0, bug: 0, performance: 0, maintainability: 0, style: 0 },
  statuses: { open: 0, fixed: 0, dismissed: 0, false_positive: 0 },
  trend: [],
  projects: [],
};

async function loadInsights(): Promise<{ data: InsightsResponse; error?: string }> {
  try {
    return { data: await api.getInsights("30d") };
  } catch (cause) {
    return {
      data: EMPTY_INSIGHTS,
      error: cause instanceof Error ? cause.message : "Could not reach the API.",
    };
  }
}

export default async function InsightsPage() {
  const result = await loadInsights();
  return (
    <>
      <TopBar breadcrumb={[{ label: "common.platform", href: "/" }, "common.insights"]}>
        <DataLink />
      </TopBar>
      <InsightsDashboard initial={result.data} initialError={result.error} />
    </>
  );
}
