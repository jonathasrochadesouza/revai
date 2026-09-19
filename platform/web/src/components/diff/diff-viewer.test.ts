import { describe, expect, it } from "vitest";

import { parseUnifiedPatch, toSplitRows } from "@/components/diff/diff-viewer";

const PATCH = [
  "diff --git a/app.py b/app.py",
  "index 1234..5678 100644",
  "--- a/app.py",
  "+++ b/app.py",
  "@@ -1,4 +1,5 @@",
  " context line",
  "-old line one",
  "-old line two",
  "+new line one",
  "+new line two",
  "+added tail",
].join("\n");

describe("parseUnifiedPatch", () => {
  it("tracks old and new line numbers through a hunk", () => {
    const rows = parseUnifiedPatch(PATCH);

    expect(rows).toEqual([
      { kind: "context", oldNumber: 1, newNumber: 1, text: "context line" },
      { kind: "del", oldNumber: 2, text: "old line one" },
      { kind: "del", oldNumber: 3, text: "old line two" },
      { kind: "add", newNumber: 2, text: "new line one" },
      { kind: "add", newNumber: 3, text: "new line two" },
      { kind: "add", newNumber: 4, text: "added tail" },
    ]);
  });

  it("resets the counters at every hunk header", () => {
    const patch = [
      "@@ -10,1 +10,1 @@",
      " context",
      "@@ -50,2 +50,2 @@",
      " second hunk context",
    ].join("\n");

    const [first, second] = parseUnifiedPatch(patch);

    expect(first?.oldNumber).toBe(10);
    expect(first?.newNumber).toBe(10);
    expect(second?.oldNumber).toBe(50);
    expect(second?.newNumber).toBe(50);
  });

  it("keeps no-newline markers out of the line counters", () => {
    const patch = ["@@ -1,1 +1,1 @@", "-old", "\\ No newline at end of file", "+new"].join("\n");

    const rows = parseUnifiedPatch(patch);

    expect(rows[0]).toMatchObject({ kind: "del", oldNumber: 1 });
    expect(rows[1]).toMatchObject({ kind: "no-newline" });
    expect(rows[2]).toMatchObject({ kind: "add", newNumber: 1 });
  });
});

describe("toSplitRows", () => {
  it("pairs consecutive deletions with additions", () => {
    const rows = toSplitRows(parseUnifiedPatch(PATCH));

    expect(rows).toEqual([
      {
        left: { number: 1, text: "context line", kind: "context" },
        right: { number: 1, text: "context line", kind: "context" },
      },
      {
        left: { number: 2, text: "old line one", kind: "del" },
        right: { number: 2, text: "new line one", kind: "add" },
      },
      {
        left: { number: 3, text: "old line two", kind: "del" },
        right: { number: 3, text: "new line two", kind: "add" },
      },
      { right: { number: 4, text: "added tail", kind: "add" } },
    ]);
  });

  it("flushes unmatched deletions as left-only rows", () => {
    const rows = toSplitRows(parseUnifiedPatch("@@ -1,2 +1,0 @@\n-removed one\n-removed two\n"));

    expect(rows).toEqual([
      { left: { number: 1, text: "removed one", kind: "del" } },
      { left: { number: 2, text: "removed two", kind: "del" } },
    ]);
  });
});
