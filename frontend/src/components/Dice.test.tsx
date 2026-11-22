import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DayStrip } from "./DayStrip";
import { DieTray, PointMeter } from "./Dice";

describe("DieTray", () => {
  it("rolls the die of its stage when pressed", () => {
    const onRoll = vi.fn().mockReturnValue(new Promise<boolean>(() => undefined));
    render(
      <ul>
        <DieTray stage="analysis" die={undefined} disabled={false} onRoll={onRoll} />
      </ul>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Roll the Analysis die" }));

    expect(onRoll).toHaveBeenCalledWith("analysis");
    expect(screen.getByRole("button", { name: "Roll the Analysis die" })).toBeDisabled();
    expect(screen.getByText("Rolling")).toBeInTheDocument();
  });

  it("lets the player try again right away when the roll failed", async () => {
    const onRoll = vi.fn().mockResolvedValue(false);
    render(
      <ul>
        <DieTray stage="analysis" die={undefined} disabled={false} onRoll={onRoll} />
      </ul>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Roll the Analysis die" }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Roll the Analysis die" })).toBeEnabled(),
    );
    expect(screen.getByText("Press to roll")).toBeInTheDocument();
  });

  it("cannot be rolled while the game has not started", () => {
    render(
      <ul>
        <DieTray stage="testing" die={undefined} disabled onRoll={vi.fn()} />
      </ul>,
    );

    expect(screen.getByRole("button", { name: "Roll the Testing die" })).toBeDisabled();
  });

  it("shows the rolled value and the points that are left", () => {
    render(
      <ul>
        <DieTray
          stage="development"
          die={{ stage: "development", day: 2, value: 5, points_left: 3 }}
          disabled={false}
          onRoll={vi.fn()}
        />
      </ul>,
    );

    expect(screen.getByRole("img", { name: "Development die shows 5" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "3 of 5 points left" })).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("PointMeter", () => {
  it("fills one square per point left", () => {
    const { container } = render(<PointMeter total={6} left={2} />);

    expect(container.querySelectorAll("i")).toHaveLength(6);
    expect(container.querySelectorAll("i.on")).toHaveLength(2);
  });
});

describe("DayStrip", () => {
  it("names the day and how many days there are", () => {
    render(<DayStrip day={3} />);

    expect(screen.getByText("Day 3 of 8")).toBeInTheDocument();
  });

  it("says the game is waiting before day one", () => {
    render(<DayStrip day={0} />);

    expect(screen.getByText("Waiting to start")).toBeInTheDocument();
  });
});
