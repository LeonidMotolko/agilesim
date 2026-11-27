import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Board, Card, SpendResult } from "../types/api";
import { SpendPanel, describeSpend } from "./PlayPage";

function card(overrides: Partial<Card> = {}): Card {
  return {
    id: "c1",
    number: 104,
    title: "Pitch deck upload",
    value: 100,
    is_emergency: false,
    stage: "development",
    state: "in_progress",
    is_blocked: false,
    squares_left: { analysis: 0, development: 2, testing: 3 },
    ...overrides,
  };
}

function resultOf(overrides: Partial<SpendResult> = {}, cardOverrides: Partial<Card> = {}) {
  return {
    card: card(cardOverrides),
    points_spent: 1,
    squares_crossed: 0,
    points_lost_to_rounding: 0,
    points_left: 4,
    replayed: false,
    ...overrides,
  } satisfies SpendResult;
}

describe("describeSpend", () => {
  it("says that the card is unblocked once the last block point is spent", () => {
    const message = describeSpend(card({ is_blocked: true }), resultOf({ points_left: 1 }));
    expect(message).toBe("ID-104 is unblocked; 1 point left");
  });

  it("says that the points went to the block while the card stays blocked", () => {
    const blocked = card({ is_blocked: true });
    const message = describeSpend(blocked, resultOf({}, { is_blocked: true }));
    expect(message).toBe("Points went to unblocking ID-104; 4 points left");
  });

  it("counts crossed squares with the right plural", () => {
    expect(describeSpend(card(), resultOf({ squares_crossed: 1 }))).toBe(
      "Crossed out 1 square; 4 points left",
    );
    expect(describeSpend(card(), resultOf({ squares_crossed: 2 }))).toBe(
      "Crossed out 2 squares; 4 points left",
    );
  });
});

describe("SpendPanel after the game", () => {
  const board: Board = {
    team_id: "t1",
    day: 8,
    wip_limits_enabled: true,
    cards: [card()],
    wip: [],
    dice: [{ stage: "development", day: 8, value: 5, points_left: 3 }],
  };

  it("explains why points can no longer be spent and disables the button", () => {
    render(<SpendPanel board={board} selectedId="c1" busy={false} finished onSpend={vi.fn()} />);

    expect(screen.getByText(/the game is over/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Spend" })).toBeDisabled();
  });
});
