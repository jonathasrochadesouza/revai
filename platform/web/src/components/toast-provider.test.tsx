import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider, useToast } from "@/components/toast-provider";
import { toastStore } from "@/components/toast-provider";

function Probe({ fire }: { fire: (push: (message: string) => void) => void }) {
  const { push } = useToast();
  return (
    <button type="button" onClick={() => fire(push)}>
      fire
    </button>
  );
}

function renderProbe(fire: (push: (message: string) => void) => void) {
  const rendered = render(
    <ToastProvider>
      <Probe fire={fire} />
    </ToastProvider>,
  );
  // The queue only fills from a user-like event; firing keeps the flow honest.
  fireEvent.click(rendered.getByText("fire"));
  return rendered;
}

function toastElement(text: string): HTMLElement | null {
  // Toasts portal into document.body, so queries must not be scoped to the
  // render container — screen.* already searches the whole body.
  return screen.queryByText(text);
}

afterEach(() => {
  cleanup();
  toastStore.clear();
  vi.useRealTimers();
});

describe("toast provider", () => {
  it("evicts the oldest toast when a fourth arrives", () => {
    renderProbe((push) => {
      push("first");
      push("second");
      push("third");
      push("fourth");
    });

    expect(toastElement("first")).toBeNull();
    expect(toastElement("second")).not.toBeNull();
    expect(toastElement("third")).not.toBeNull();
    expect(toastElement("fourth")).not.toBeNull();
  });

  it("auto-dismisses after the countdown", () => {
    vi.useFakeTimers();
    renderProbe((push) => push("temporary"));

    expect(toastElement("temporary")).not.toBeNull();
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    // Exit animation window, then gone.
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(toastElement("temporary")).toBeNull();
  });

  it("pauses on hover and resumes for the remaining time", () => {
    vi.useFakeTimers();
    renderProbe((push) => push("hovered"));

    act(() => {
      vi.advanceTimersByTime(8_000);
    });
    // 2 s remain. Hovering pauses the countdown.
    fireEvent.mouseEnter(screen.getByText("hovered").closest('[role="status"]')!);
    act(() => {
      vi.advanceTimersByTime(5_000);
    });
    expect(toastElement("hovered")).not.toBeNull();

    // Leaving resumes only for what was left.
    fireEvent.mouseLeave(screen.getByText("hovered").closest('[role="status"]')!);
    act(() => {
      vi.advanceTimersByTime(1_900);
    });
    expect(toastElement("hovered")).not.toBeNull();
    act(() => {
      vi.advanceTimersByTime(200);
    });
    act(() => {
      vi.advanceTimersByTime(400);
    });
    expect(toastElement("hovered")).toBeNull();
  });

  it("exposes the dismiss affordance translated through the UI locale", () => {
    renderProbe((push) => push("message"));

    // en-US is the default locale of the unmounted preference provider.
    expect(screen.getByLabelText("Dismiss notification")).not.toBeNull();
  });
});
