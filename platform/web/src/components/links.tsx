"use client";

import Link from "next/link";

import { useUiText } from "@/components/ui-preference-bootstrap";

/** Settings shortcut rendered from server pages, translated client-side. */
export function EngineLink({ className = "" }: { className?: string }) {
  const { t } = useUiText();
  return (
    <Link href="/settings/engine" className={`rounded-control border border-line-strong px-3 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink ${className}`}>
      {t("common.engine")}
    </Link>
  );
}

export function DataLink({ className = "" }: { className?: string }) {
  const { t } = useUiText();
  return (
    <Link href="/settings/data" className={`rounded-control border border-line-strong px-3 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink ${className}`}>
      {t("data.title")}
    </Link>
  );
}

export function AllProjectsLink() {
  const { t } = useUiText();
  return (
    <Link
      href="/"
      className="rounded-control border border-line-strong px-3 py-2 text-[12px] font-medium text-ink-muted hover:bg-canvas hover:text-ink"
    >
      ← {t("common.allProjects")}
    </Link>
  );
}

export function BackToProjectsLink() {
  const { t } = useUiText();
  return (
    <Link href="/" className="mt-4 inline-block text-[12px] font-medium text-low hover:underline">
      {t("common.backToProjects")}
    </Link>
  );
}

export function BackToDashboardLink() {
  const { t } = useUiText();
  return (
    <p className="mt-4 text-[12.5px] text-ink-muted">
      <Link href="/" className="text-low hover:underline">
        {t("settings.engine.backToDashboard")}
      </Link>
    </p>
  );
}
