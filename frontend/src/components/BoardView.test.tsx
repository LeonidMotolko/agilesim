import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Board, Card } from "../types/api";
import { BoardView } from "./BoardView";

function card(overrides: Partial<Card> = {}): Card {
  return {
    id: "c1",
    number: 101,
    title: "Landing page copy",
    value: 30,
    is_emergency: false,
    stage: "analysis",
    state: "in_progress",
    is_blocked: false,
    squares_left: { analysis: 1, development: 4, testing: 3 },
    ...overrides,
  };
}

function boardOf(cards: Card[], overrides: Partial<Board> = {}): Board {
  return {
    team_id: "t1",
    day: 2,
    wip_limits_enabled: false,
    cards,
    wip: [{ stage: "analysis", count: cards.length, limit: 2 }],
    dice: [],
    ...overrides,
  };
}

describe("BoardView", () => {
  afterEach(() => {
    delete (HTMLElement.prototype as { animate?: unknown }).animate;
  });

  it("puts every card in the column of its stage", () => {
    render(<BoardView board={boardOf([card(), card({ id: "c2", number: 102, stage: "done" })])} />);

    expect(within(screen.getByLabelText("Analysis")).getByText("ID-101")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Done")).getByText("ID-102")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Testing")).getByText("Nothing here yet")).toBeVisible();
  });

  it("shows no buttons to a viewer and a move button to a player", () => {
    const { rerender } = render(<BoardView board={boardOf([card()])} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();

    const onMove = vi.fn();
    rerender(<BoardView board={boardOf([card()])} onMove={onMove} onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Move to Development" }));

    expect(onMove).toHaveBeenCalledWith(expect.objectContaining({ id: "c1" }), "development");
  });

  it("shortens a long row of squares to four boxes and the rest as a number", () => {
    const long = card({ squares_left: { analysis: 8, development: 5, testing: 1 } });
    const { container } = render(<BoardView board={boardOf([long])} />);

    const rows = container.querySelectorAll(".squares li");
    expect(rows[0]?.querySelectorAll("i")).toHaveLength(4);
    expect(rows[0]?.querySelector(".sq-more")).toHaveTextContent("+4");
    expect(rows[1]?.querySelectorAll("i")).toHaveLength(5);
    expect(rows[1]?.querySelector(".sq-more")).toBeNull();
  });

  it("offers Work on it only for cards in a work stage", () => {
    const cards = [
      card(),
      card({ id: "c2", number: 102, stage: "backlog", squares_left: {} }),
      card({ id: "c3", number: 103, stage: "done", squares_left: {} }),
    ];
    render(<BoardView board={boardOf(cards)} onMove={vi.fn()} onSelect={vi.fn()} />);

    expect(screen.getAllByRole("button", { name: "Work on it" })).toHaveLength(1);
  });

  it("marks a column that is over its limit once the limits are on", () => {
    const cards = [card(), card({ id: "c2", number: 102 }), card({ id: "c3", number: 103 })];
    const { container, rerender } = render(<BoardView board={boardOf(cards)} />);
    expect(container.querySelector(".wip-over")).toBeNull();

    rerender(<BoardView board={boardOf(cards, { wip_limits_enabled: true })} />);
    expect(container.querySelector(".wip-over")).not.toBeNull();
  });

  it("animates a card that arrives in another column, but not the first render", () => {
    const animate = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "animate", {
      value: animate,
      configurable: true,
    });
    const { rerender } = render(<BoardView board={boardOf([card()])} />);
    expect(animate).not.toHaveBeenCalled();

    rerender(<BoardView board={boardOf([card({ stage: "development" })])} />);
    expect(animate).toHaveBeenCalledTimes(1);

    rerender(<BoardView board={boardOf([card({ stage: "development" })])} />);
    expect(animate).toHaveBeenCalledTimes(1);
  });
});
