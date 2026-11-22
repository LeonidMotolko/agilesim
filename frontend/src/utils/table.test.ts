import { describe, expect, it } from "vitest";

import { filterRows, sortRows } from "./table";

const rows = [
  { name: "Beta", points: 20, lead: 3 },
  { name: "Alpha", points: 50, lead: null },
  { name: "Gamma", points: 10, lead: 2 },
];

describe("filterRows", () => {
  it("keeps rows containing the query, ignoring case and spaces around it", () => {
    expect(filterRows(rows, "  ALP ", (row) => row.name).map((row) => row.name)).toEqual(["Alpha"]);
  });

  it("returns every row for an empty query", () => {
    expect(filterRows(rows, "", (row) => row.name)).toHaveLength(3);
  });
});

describe("sortRows", () => {
  it("sorts text and numbers in both directions without touching the input", () => {
    expect(sortRows(rows, (row) => row.name, "asc").map((row) => row.name)).toEqual([
      "Alpha",
      "Beta",
      "Gamma",
    ]);
    expect(sortRows(rows, (row) => row.points, "desc").map((row) => row.points)).toEqual([
      50, 20, 10,
    ]);
    expect(rows[0]?.name).toBe("Beta");
  });

  it("puts empty values last whatever the direction", () => {
    expect(sortRows(rows, (row) => row.lead, "asc").map((row) => row.lead)).toEqual([2, 3, null]);
    expect(sortRows(rows, (row) => row.lead, "desc").map((row) => row.lead)).toEqual([3, 2, null]);
  });
});
