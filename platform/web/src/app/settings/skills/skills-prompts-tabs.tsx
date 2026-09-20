/**
 * Settings › Skills & Prompts — the two top-level tabs.
 *
 * "Skills" is the marketplace + installed list; "Prompts" is the existing
 * default-prompts and scenarios editing, unchanged in behaviour. The tab bar
 * is a plain button row with `role="tablist"` semantics — there is no routing
 * behind it, so no URL state to keep in sync.
 */

"use client";

import { useState } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";
import type {
  ConfigResponse,
  InstalledSkill,
  PromptsResponse,
} from "@/lib/api";

import { PromptsForm } from "./prompts-form";
import { SkillsTab } from "./skills-tab";

interface TabsProps {
  initial: PromptsResponse;
  config: ConfigResponse["config"];
  skills: InstalledSkill[];
}

type Tab = "skills" | "prompts";

export function SkillsPromptsTabs({ initial, config, skills }: TabsProps) {
  const { t } = useUiText();
  const [tab, setTab] = useState<Tab>("skills");

  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "skills", label: t("skills.tab.skills"), count: skills.length },
    { id: "prompts", label: t("skills.tab.prompts") },
  ];

  return (
    <>
      <div
        role="tablist"
        aria-label={t("settings.prompts.title")}
        className="mb-4 flex w-fit gap-1 rounded-control border border-line bg-canvas p-1"
      >
        {tabs.map((entry) => {
          const active = entry.id === tab;
          return (
            <button
              key={entry.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(entry.id)}
              className={`flex items-center gap-1.5 rounded-control px-4 py-1.5 text-[12.5px] font-semibold transition-colors ${
                active
                  ? "bg-paper text-ink shadow-sm"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {entry.label}
              {entry.count !== undefined && (
                <span className="rounded-full bg-line px-1.5 text-[10.5px] font-bold text-ink-muted">
                  {entry.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" hidden={tab !== "skills"}>
        {tab === "skills" && <SkillsTab initial={skills} />}
      </div>
      <div role="tabpanel" hidden={tab !== "prompts"}>
        {tab === "prompts" && <PromptsForm initial={initial} config={config} />}
      </div>
    </>
  );
}
