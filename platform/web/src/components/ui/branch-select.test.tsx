import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BranchSelect } from "@/components/ui/branch-select";

const branches = ["main", "release"];

function ReviewBranches({
  onBaseChange,
  onHeadChange,
}: {
  onBaseChange: (branch: string) => void;
  onHeadChange: (branch: string) => void;
}) {
  const [base, setBase] = useState("main");
  const [head, setHead] = useState("release");

  return (
    <>
      <BranchSelect
        label="review.base"
        value={base}
        branches={branches}
        onChange={(branch) => {
          onBaseChange(branch);
          setBase(branch);
        }}
      />
      <BranchSelect
        label="review.head"
        value={head}
        branches={branches}
        onChange={(branch) => {
          onHeadChange(branch);
          setHead(branch);
        }}
      />
    </>
  );
}

describe("BranchSelect", () => {
  afterEach(cleanup);

  it("does not emit changes when the current Base or Head is selected again", async () => {
    const user = userEvent.setup();
    const onBaseChange = vi.fn();
    const onHeadChange = vi.fn();

    render(<ReviewBranches onBaseChange={onBaseChange} onHeadChange={onHeadChange} />);

    await user.click(screen.getByRole("button", { name: "Base main" }));
    await user.click(screen.getByRole("option", { name: "main" }));
    expect(onBaseChange).not.toHaveBeenCalled();
    expect(screen.queryByRole("listbox")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Head release" }));
    await user.click(screen.getByRole("option", { name: "release" }));
    expect(onHeadChange).not.toHaveBeenCalled();
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("keeps options out of the tab order and closes the popup when tabbing away", async () => {
    const user = userEvent.setup();

    render(<ReviewBranches onBaseChange={vi.fn()} onHeadChange={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Base main" }));
    expect(screen.getByRole("option", { name: "main" }).getAttribute("tabindex")).toBe("-1");

    await user.tab();
    expect(screen.queryByRole("listbox")).toBeNull();
  });
});
