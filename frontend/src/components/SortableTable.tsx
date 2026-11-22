import { useMemo, useState, type ReactNode } from "react";

import { sortRows, type SortDirection, type SortValue } from "../utils/table";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** Makes the column sortable. */
  sortValue?: (row: T) => SortValue;
}

interface SortableTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  emptyText: string;
  caption?: string;
  initialSort?: { key: string; direction: SortDirection };
}

export function SortableTable<T>({
  columns,
  rows,
  rowKey,
  emptyText,
  caption,
  initialSort,
}: SortableTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; direction: SortDirection } | null>(
    initialSort ?? null,
  );

  const sorted = useMemo(() => {
    const column = columns.find((candidate) => candidate.key === sort?.key);
    if (sort === null || column?.sortValue === undefined) {
      return rows;
    }
    return sortRows(rows, column.sortValue, sort.direction);
  }, [columns, rows, sort]);

  const toggle = (key: string) => {
    setSort((current) =>
      current?.key === key && current.direction === "asc"
        ? { key, direction: "desc" }
        : { key, direction: "asc" },
    );
  };

  return (
    <div className="table-wrap">
      <table>
        {caption ? <caption>{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                aria-sort={
                  sort?.key === column.key
                    ? sort.direction === "asc"
                      ? "ascending"
                      : "descending"
                    : undefined
                }
              >
                {column.sortValue ? (
                  <button type="button" className="link-button" onClick={() => toggle(column.key)}>
                    {column.header}
                    {sort?.key === column.key ? (sort.direction === "asc" ? " ▲" : " ▼") : ""}
                  </button>
                ) : (
                  column.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={columns.length}>{emptyText}</td>
            </tr>
          ) : (
            sorted.map((row) => (
              <tr key={rowKey(row)}>
                {columns.map((column) => (
                  <td key={column.key}>{column.render(row)}</td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
