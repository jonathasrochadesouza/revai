/**
 * DiffViewer — the proposed review context, unified or side by side.
 *
 * The unified view renders the raw unified-diff text with tone-by-prefix.
 * The split view parses the same patch into (old, new) row pairs so a hunk's
 * deletions and additions align line by line — the parse is a pure exported
 * function, unit-testable against tricky payloads (no-newline markers, empty
 * hunks, paired del/add sequences).
 */

"use client";

import { Check } from "lucide-react";
import { useMemo, useState } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";
import type { DiffPreview } from "@/lib/api";

type DiffRowKind = "meta" | "context" | "add" | "del" | "no-newline";

interface DiffRow {
  kind: DiffRowKind;
  oldNumber?: number;
  newNumber?: number;
  text: string;
}

/** Parse a unified diff into annotated rows with tracked line numbers. */
export function parseUnifiedPatch(patch: string): DiffRow[] {
  const rows: DiffRow[] = [];
  let oldNumber = 0;
  let newNumber = 0;

  for (const raw of patch.split("\n")) {
    if (raw === "" || raw.startsWith("diff ") || raw.startsWith("index ") || raw.startsWith("--- ") || raw.startsWith("+++ ")) {
      continue; // separators and file headers carry no row of their own
    }
    if (raw.startsWith("@@")) {
      // Hunk headers carry the line counters; nothing to display.
      const match = /@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(raw);
      if (match) {
        oldNumber = Number(match[1]);
        newNumber = Number(match[2]);
      }
      continue;
    }
    if (raw.startsWith("+")) {
      rows.push({ kind: "add", newNumber: newNumber++, text: raw.slice(1) });
      continue;
    }
    if (raw.startsWith("-")) {
      rows.push({ kind: "del", oldNumber: oldNumber++, text: raw.slice(1) });
      continue;
    }
    if (raw.startsWith("\\")) {
      rows.push({ kind: "no-newline", text: raw });
      continue;
    }
    if (raw.startsWith(" ")) {
      rows.push({ kind: "context", oldNumber: oldNumber++, newNumber: newNumber++, text: raw.slice(1) });
      continue;
    }
    if (raw === "") {
      continue;
    }
    rows.push({ kind: "meta", text: raw });
  }
  return rows;
}

interface SplitSide {
  number?: number;
  text: string;
  kind: DiffRowKind;
}

interface SplitRow {
  left?: SplitSide;
  right?: SplitSide;
}

/** Pair deletions with additions for the side-by-side rendering. */
export function toSplitRows(rows: DiffRow[]): SplitRow[] {
  const split: SplitRow[] = [];
  let pendingDeletes: SplitSide[] = [];

  const flushDeletes = () => {
    for (const del of pendingDeletes) {
      split.push({ left: del });
    }
    pendingDeletes = [];
  };

  for (const row of rows) {
    switch (row.kind) {
      case "del": {
        pendingDeletes.push({ number: row.oldNumber, text: row.text, kind: "del" });
        break;
      }
      case "add": {
        const del = pendingDeletes.shift();
        split.push(
          del
            ? { left: del, right: { number: row.newNumber, text: row.text, kind: "add" } }
            : { right: { number: row.newNumber, text: row.text, kind: "add" } },
        );
        break;
      }
      case "context": {
        flushDeletes();
        split.push({
          left: { number: row.oldNumber, text: row.text, kind: "context" },
          right: { number: row.newNumber, text: row.text, kind: "context" },
        });
        break;
      }
      case "meta":
      case "no-newline": {
        flushDeletes();
        // Annotation bands span both sides so the reading flow is kept.
        split.push({
          left: { text: row.text, kind: "meta" },
          right: { text: "", kind: "meta" },
        });
        break;
      }
    }
  }
  flushDeletes();
  return split;
}

function LoadingRows() {
  const { t } = useUiText();
  return (
    <div className="space-y-2" aria-label={t("review.loadingRepository")}>
      {[70, 92, 58, 80].map((width) => (
        <div
          key={width}
          className="h-5 animate-pulse rounded-chip bg-canvas"
          style={{ width: `${width}%` }}
        />
      ))}
    </div>
  );
}

export function DiffViewer({
  preview,
  loading,
}: {
  preview: DiffPreview | null;
  loading: boolean;
}) {
  const { t } = useUiText();
  const [view, setView] = useState<"unified" | "split">("unified");

  if (loading && !preview) {
    return <div className="p-4"><LoadingRows /></div>;
  }

  if (!preview?.patch) {
    return (
      <div className="grid min-h-[360px] place-items-center p-8 text-center">
        <div>
          <Check className="mx-auto mb-3 size-7 text-success" strokeWidth={1.7} />
          <p className="mb-1 text-[12.5px] font-semibold">{t("review.noChanges")}</p>
          <p className="text-[11px] text-ink-muted">
            {t("review.noChangesDetail")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="absolute right-2 top-2 z-10 flex overflow-hidden rounded-control border border-line-strong bg-paper text-[10px] font-semibold">
        {(["unified", "split"] as const).map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={view === option}
            onClick={() => setView(option)}
            className={`px-2.5 py-1 transition-colors ${
              view === option ? "bg-ink text-paper" : "text-ink-muted hover:bg-canvas"
            }`}
          >
            {t(`review.diffView.${option}`)}
          </button>
        ))}
      </div>

      {view === "unified" ? <UnifiedPatch preview={preview} /> : <SplitPatch preview={preview} />}

      {preview.truncated && (
        <p className="sticky bottom-0 border-t border-medium-line bg-medium-surface px-4 py-2 text-[10.5px] text-medium">
          {t("review.diffTruncated")}
        </p>
      )}
    </div>
  );
}

function UnifiedPatch({ preview }: { preview: DiffPreview }) {
  const rows = useMemo(() => preview.patch.split("\n"), [preview.patch]);
  return (
    <div className="max-h-[360px] overflow-auto bg-sunken">
      <pre className="min-w-max py-2 text-[11px] leading-[1.65]">
        {rows.map((line, index) => {
          const tone = line.startsWith("+")
            ? "bg-success-surface text-success"
            : line.startsWith("-")
              ? "bg-critical-surface text-critical"
              : line.startsWith("@@")
                ? "bg-low-surface text-low"
                : line.startsWith("diff ") || line.startsWith("index ")
                  ? "font-semibold text-ink"
                  : "text-ink-muted";
          return (
            <code
              key={`${index}-${line}`}
              className={`block min-h-[18px] px-4 ${tone}`}
            >
              {line || " "}
            </code>
          );
        })}
      </pre>
    </div>
  );
}

const ROW_TONES: Record<DiffRowKind, string> = {
  meta: "font-semibold text-ink bg-canvas",
  context: "text-ink-muted",
  add: "bg-success-surface text-success",
  del: "bg-critical-surface text-critical",
  "no-newline": "text-ink-subtle",
};

function SplitPatch({ preview }: { preview: DiffPreview }) {
  const rows = useMemo(() => toSplitRows(parseUnifiedPatch(preview.patch)), [preview.patch]);
  return (
    <div className="max-h-[360px] overflow-auto bg-sunken">
      <table className="w-full table-fixed border-collapse font-mono text-[11px] leading-[1.65]">
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              <td className="w-10 min-w-10 select-none border-r border-line bg-canvas px-1.5 text-right text-ink-subtle">
                {row.left?.number ?? ""}
              </td>
              <td
                className={`min-w-0 whitespace-pre-wrap break-all px-3 ${
                  row.left ? ROW_TONES[row.left.kind] : "text-ink-subtle"
                }`}
              >
                {row.left?.text || " "}
              </td>
              <td className="w-1 border-x border-line bg-canvas" />
              <td className="w-10 min-w-10 select-none bg-canvas px-1.5 text-right text-ink-subtle">
                {row.right?.number ?? ""}
              </td>
              <td
                className={`min-w-0 whitespace-pre-wrap break-all px-3 ${
                  row.right ? ROW_TONES[row.right.kind] : "text-ink-subtle"
                }`}
              >
                {row.right?.text || " "}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
