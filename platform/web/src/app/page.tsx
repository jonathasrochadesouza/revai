/**
 * Phase 0 landing page.
 *
 * Two jobs, both deliberate:
 *   1. Prove the frontend and backend actually talk to each other.
 *   2. Show the Paper Light design system rendered as real components rather
 *      than as a static mock.
 *
 * A server component, so the API call happens in Node and a cold backend
 * produces a helpful page instead of a client-side error.
 */

import Link from "next/link";

import { Logo } from "@/components/logo";
import { TopBar } from "@/components/top-bar";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardRow } from "@/components/ui/card";
import { API_BASE_URL, probeBackend } from "@/lib/api";

/** Roadmap, mirrored from docs/ARCHITECTURE.md §6. */
const PHASES = [
  { n: 0, name: "Skeleton", detail: "Scaffold, theme, health check", done: true },
  {
    n: 1,
    name: "Storage & config",
    detail: "YAML repositories, atomic writes",
    done: true,
  },
  { n: 2, name: "Providers", detail: "OpenRouter, detection, onboarding" },
  { n: 3, name: "Projects & git", detail: "Open local, clone, diff preview" },
  { n: 4, name: "Deterministic pipeline", detail: "Linters, AST — zero tokens" },
  { n: 5, name: "AI stage", detail: "Streaming, pipeline & event stream" },
  { n: 6, name: "Results", detail: "Findings, split diff, patches" },
  { n: 7, name: "Export & insights", detail: "JSON, Markdown, HTML, metrics" },
] as const;

const SEVERITIES = [
  { tone: "critical", label: "Critical", meaning: "Bugs, security, leaks" },
  { tone: "medium", label: "Medium", meaning: "SOLID, performance, smells" },
  { tone: "low", label: "Low", meaning: "Naming, formatting" },
] as const;

const TOKENS = [
  ["#fafafa", "canvas"],
  ["#ffffff", "paper"],
  ["#09090b", "ink"],
  ["#e4e4e7", "line"],
  ["#dc2626", "critical"],
  ["#d97706", "medium"],
  ["#2563eb", "low"],
  ["#059669", "success"],
] as const;

const GUARANTEES = [
  "Runs on 127.0.0.1 only. No account, no telemetry.",
  "Source code never leaves this machine.",
  "Never writes to your repository — fixes are patches you apply.",
  "State is plain YAML you can read, diff and version.",
] as const;

export default async function Home() {
  const state = await probeBackend();

  return (
    <>
      <TopBar breadcrumb={["Platform", "Phase 1"]}>
        <Link
          href="/settings/engine"
          className="rounded-control border border-line-strong px-3 py-1.5 text-[12.5px] font-medium text-ink-muted transition-colors hover:bg-canvas hover:text-ink"
        >
          Settings
        </Link>
        {state.connected ? (
          <Badge tone="success" dot>
            API connected
          </Badge>
        ) : (
          <Badge tone="critical" dot>
            API unreachable
          </Badge>
        )}
      </TopBar>

      <main className="mx-auto max-w-[1180px] px-7 pb-20 pt-9">
        {/* ---------------- heading ---------------- */}
        <div className="mb-8">
          <p className="eyebrow mb-2">RevAI Platform · 3.0.0-alpha</p>
          <h1 className="mb-2.5 text-[29px] font-bold tracking-[-0.9px]">
            Configuration is persistent.
          </h1>
          <p className="max-w-[64ch] text-[14.5px] leading-relaxed text-ink-muted">
            Phase 1 landed: settings now live in{" "}
            <code className="rounded-xs bg-canvas px-1.5 py-0.5 text-[13px] text-low">
              ~/.revai/config.yaml
            </code>
            , written atomically so a failed save can never corrupt what was already
            there. Open{" "}
            <Link href="/settings/engine" className="font-medium text-low hover:underline">
              Settings › Engine
            </Link>{" "}
            to try it.
          </p>
        </div>

        <div className="grid gap-3.5 lg:grid-cols-[1fr_340px]">
          {/* ---------------- left column ---------------- */}
          <div className="flex flex-col gap-3.5">
            {/* backend connection */}
            <Card>
              <CardHeader
                title="Backend connection"
                icon={
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    className="size-[15px]"
                  >
                    <rect x="2" y="2" width="20" height="8" rx="2" />
                    <rect x="2" y="14" width="20" height="8" rx="2" />
                    <path d="M6 6h.01M6 18h.01" />
                  </svg>
                }
                aside={API_BASE_URL}
              />
              <CardBody>
                {state.connected ? (
                  <>
                    <CardRow label="Status" hint="Live response from /api/health">
                      <Badge tone="success" dot>
                        {state.health.status}
                      </Badge>
                    </CardRow>
                    <CardRow label="Version" hint="Reported by the API">
                      <span className="numeric text-[13px] text-ink-muted">
                        {state.health.version}
                      </span>
                    </CardRow>
                    <CardRow label="Python" hint={state.runtime.platform}>
                      <span className="numeric text-[13px] text-ink-muted">
                        {state.runtime.python_version}
                      </span>
                    </CardRow>
                    <CardRow
                      label="Data directory"
                      hint="Projects, reviews and config live here as plain YAML"
                    >
                      <span className="flex items-center gap-2.5">
                        <code className="rounded-xs bg-canvas px-2 py-1 text-[11.5px] text-ink-muted">
                          {state.runtime.data_dir}
                        </code>
                        <Badge
                          tone={
                            state.runtime.data_dir_exists ? "success" : "medium"
                          }
                        >
                          {state.runtime.data_dir_exists ? "ready" : "missing"}
                        </Badge>
                      </span>
                    </CardRow>
                  </>
                ) : (
                  <div className="rounded-control border border-critical-line bg-critical-surface p-4">
                    <p className="mb-2 text-[13.5px] font-semibold text-critical">
                      Could not reach the API
                    </p>
                    <p className="mb-3 text-[12.5px] leading-relaxed text-ink-muted">
                      {state.reason}
                    </p>
                    <p className="mb-2 text-[12.5px] text-ink-muted">
                      Start it in a second terminal:
                    </p>
                    <pre className="overflow-x-auto rounded-chip border border-line bg-paper px-3 py-2.5 text-[11.5px] leading-relaxed">
                      {"cd platform/api\nuv sync --all-groups\nuv run revai-api"}
                    </pre>
                  </div>
                )}
              </CardBody>
            </Card>

            {/* roadmap */}
            <Card>
              <CardHeader
                title="Roadmap"
                icon={
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    className="size-[15px]"
                  >
                    <path d="M22 11.1V12a10 10 0 1 1-5.9-9.1" />
                    <polyline points="22 4 12 14 9 11" />
                  </svg>
                }
                aside={`${PHASES.filter((p) => "done" in p).length} of ${PHASES.length} complete`}
              />
              <CardBody>
                <ol className="pt-0.5">
                  {PHASES.map((phase, index) => {
                    const isLast = index === PHASES.length - 1;
                    const previous = PHASES[index - 1];
                    const isNext =
                      !("done" in phase) && previous && "done" in previous;
                    const isDone = "done" in phase;

                    return (
                      <li
                        key={phase.n}
                        className={`relative pl-7 ${isLast ? "" : "pb-[18px]"}`}
                      >
                        {!isLast && (
                          <span
                            aria-hidden
                            className={`absolute left-2 top-5 h-full w-px ${
                              isDone ? "bg-success" : "bg-line"
                            }`}
                          />
                        )}

                        <span
                          aria-hidden
                          className={`absolute left-0 top-0.5 grid size-[17px] place-items-center rounded-full border ${
                            isDone
                              ? "border-success bg-success"
                              : isNext
                                ? "border-2 border-ink bg-paper"
                                : "border-line-strong bg-paper"
                          }`}
                        >
                          {isDone && (
                            <svg
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="#fff"
                              strokeWidth={3.5}
                              className="size-[9px]"
                            >
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          )}
                        </span>

                        <div className="flex items-baseline gap-2.5">
                          <p
                            className={`text-[13.5px] ${
                              isDone || isNext
                                ? "font-semibold"
                                : "font-medium text-ink-subtle"
                            }`}
                          >
                            <span className="numeric mr-2 text-ink-subtle">
                              {phase.n}
                            </span>
                            {phase.name}
                          </p>
                          {isDone && <Badge tone="success">done</Badge>}
                          {isNext && <Badge tone="info">next</Badge>}
                        </div>
                        <p
                          className={`text-[12.5px] leading-snug ${
                            isDone || isNext ? "text-ink-muted" : "text-ink-subtle"
                          }`}
                        >
                          {phase.detail}
                        </p>
                      </li>
                    );
                  })}
                </ol>
              </CardBody>
            </Card>
          </div>

          {/* ---------------- right column ---------------- */}
          <aside className="flex flex-col gap-3.5">
            <Card>
              <CardHeader title="Severity scale" aside="canonical" />
              <CardBody>
                <div className="flex flex-col gap-2.5">
                  {SEVERITIES.map((s) => (
                    <div key={s.label} className="flex items-center gap-3">
                      <Badge tone={s.tone}>{s.label}</Badge>
                      <span className="text-[12.5px] text-ink-muted">
                        {s.meaning}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-4 border-t border-line pt-3.5 text-[11.5px] leading-relaxed text-ink-subtle">
                  Defined once in{" "}
                  <code className="text-[11px]">globals.css</code> so no screen
                  can invent its own mapping.
                </p>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Tokens" aside="Paper Light" />
              <CardBody className="pt-3.5">
                <div className="grid grid-cols-4 gap-1.5">
                  {TOKENS.map(([hex, name]) => (
                    <div key={name}>
                      <span
                        className="block h-9 rounded-chip border border-line"
                        style={{ backgroundColor: hex }}
                      />
                      <p className="mt-1 truncate text-[9.5px] text-ink-subtle">
                        {name}
                      </p>
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Guarantees" icon={<Logo size={15} />} />
              <CardBody className="pt-3.5">
                <ul className="flex flex-col gap-2.5 text-[12.5px] leading-relaxed text-ink-muted">
                  {GUARANTEES.map((line) => (
                    <li key={line} className="flex gap-2.5">
                      <svg
                        aria-hidden
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={2.5}
                        className="mt-0.5 size-3.5 shrink-0 text-success"
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                      {line}
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          </aside>
        </div>
      </main>
    </>
  );
}
