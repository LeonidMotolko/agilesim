import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SortableTable, type Column } from "./SortableTable";

interface Row {
  id: string;
  team: string;
  money: number;
}

const COLUMNS: Column<Row>[] = [
  { key: "team", header: "Team", render: (row) => row.team, sortValue: (row) => row.team },
  {
    key: "money",
    header: "Money",
    render: (row) => `$${row.money}`,
    sortValue: (row) => row.money,
  },
];

const ROWS: Row[] = [
  { id: "1", team: "Beta", money: 200 },
  { id: "2", team: "Alpha", money: 500 },
  { id: "3", team: "Gamma", money: 100 },
];

function teamsInOrder(): string[] {
  const body = screen.getAllByRole("rowgroup")[1];
  if (body === undefined) {
    throw new Error("table body missing");
  }
  return within(body)
    .getAllByRole("row")
    .map((row) => within(row).getAllByRole("cell")[0]?.textContent ?? "");
}

describe("SortableTable", () => {
  it("sorts by a column and reverses on the second click", () => {
    render(
      <SortableTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} emptyText="none" />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Team" }));
    expect(teamsInOrder()).toEqual(["Alpha", "Beta", "Gamma"]);

    fireEvent.click(screen.getByRole("button", { name: /Team/ }));
    expect(teamsInOrder()).toEqual(["Gamma", "Beta", "Alpha"]);
  });

  it("starts with the initial sort and marks the sorted column", () => {
    render(
      <SortableTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        emptyText="none"
        initialSort={{ key: "money", direction: "desc" }}
      />,
    );

    expect(teamsInOrder()).toEqual(["Alpha", "Beta", "Gamma"]);
    expect(screen.getByRole("columnheader", { name: /Money/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
  });

  it("shows the empty text when there are no rows", () => {
    render(
      <SortableTable
        columns={COLUMNS}
        rows={[]}
        rowKey={(row) => row.id}
        emptyText="No teams match."
      />,
    );

    expect(screen.getByText("No teams match.")).toBeInTheDocument();
  });
});
