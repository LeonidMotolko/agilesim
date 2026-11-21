export type SortDirection = "asc" | "desc";
export type SortValue = string | number | null;

/** Keep the rows whose searchable text contains the query (case-insensitive). */
export function filterRows<T>(rows: T[], query: string, text: (row: T) => string): T[] {
  const needle = query.trim().toLowerCase();
  if (needle === "") {
    return rows;
  }
  return rows.filter((row) => text(row).toLowerCase().includes(needle));
}

/** A sorted copy; empty values (null) always go last. */
export function sortRows<T>(
  rows: T[],
  value: (row: T) => SortValue,
  direction: SortDirection,
): T[] {
  const factor = direction === "asc" ? 1 : -1;
  return [...rows].sort((left, right) => {
    const a = value(left);
    const b = value(right);
    if (a === null && b === null) {
      return 0;
    }
    if (a === null) {
      return 1;
    }
    if (b === null) {
      return -1;
    }
    if (typeof a === "number" && typeof b === "number") {
      return (a - b) * factor;
    }
    return String(a).localeCompare(String(b)) * factor;
  });
}
