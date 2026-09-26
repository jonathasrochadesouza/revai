import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FindingCard } from "@/components/findings/finding-card";
import type { Finding } from "@/lib/api";

const baseFinding: Finding = {
  id: "f1",
  fingerprint: "abc123",
  severity: "medium",
  category: "bug",
  title: "Off-by-one in pagination",
  description: "The last page is skipped.",
  rationale: "",
  file: "src/pagination.ts",
  line_start: 42,
  line_end: null,
  source: "ai",
  rule_id: null,
  confidence: 0.9,
  suggested_patch: "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
  status: "open",
  fix_state: "none",
  fix_applied_at: null,
  fix_validation: null,
};

describe("FindingCard", () => {
  afterEach(cleanup);

  it("shows the Apply fix action when onFix is provided and a patch exists", () => {
    render(<FindingCard finding={baseFinding} onStatus={vi.fn()} onFix={vi.fn()} />);

    expect(screen.getByRole("button", { name: /apply fix/i })).not.toBeNull();
  });

  it("shows the Generate fix action when onFix is provided and there is no patch yet", () => {
    render(
      <FindingCard
        finding={{ ...baseFinding, suggested_patch: null }}
        onStatus={vi.fn()}
        onFix={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /generate fix/i })).not.toBeNull();
  });

  it("hides both fix actions when onFix is omitted (cloud projects have no working tree to patch)", () => {
    render(<FindingCard finding={baseFinding} onStatus={vi.fn()} />);

    expect(screen.queryByRole("button", { name: /apply fix/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /generate fix/i })).toBeNull();
  });

  it("hides both fix actions for a patch-less finding when onFix is omitted", () => {
    render(
      <FindingCard finding={{ ...baseFinding, suggested_patch: null }} onStatus={vi.fn()} />,
    );

    expect(screen.queryByRole("button", { name: /apply fix/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /generate fix/i })).toBeNull();
  });

  it("still lets the user copy the suggested patch when fix actions are hidden", () => {
    render(<FindingCard finding={baseFinding} onStatus={vi.fn()} />);

    expect(screen.getByRole("button", { name: /copy suggested patch/i })).not.toBeNull();
  });
});
