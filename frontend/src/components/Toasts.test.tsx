import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider, useToast } from "./Toasts";

function Buttons() {
  const { notify } = useToast();
  return (
    <>
      <button type="button" onClick={() => notify("Die rolled")}>
        info
      </button>
      <button type="button" onClick={() => notify("Not allowed", "error")}>
        error
      </button>
    </>
  );
}

describe("toasts", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a message and removes it after a few seconds", () => {
    render(
      <ToastProvider>
        <Buttons />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "info" }));
    expect(screen.getByRole("status")).toHaveTextContent("Die rolled");

    act(() => {
      vi.advanceTimersByTime(4100);
    });
    expect(screen.queryByText("Die rolled")).not.toBeInTheDocument();
  });

  it("announces an error as an alert and lets the person dismiss it", () => {
    render(
      <ToastProvider>
        <Buttons />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "error" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Not allowed");

    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
