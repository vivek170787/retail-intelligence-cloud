"use client";

/**
 * Generic, dense, enterprise-style data table -- compact rows, a muted
 * header, optional client-side column sorting, and integrated empty/
 * loading states. No business logic: callers supply column definitions
 * and already-fetched rows; this component only renders and (optionally)
 * sorts them.
 */

import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { EmptyState } from "@/components/retail/EmptyState";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  align?: "left" | "right" | "center";
  /** Required for a column to be sortable -- also used as the default cell renderer. */
  accessor?: (row: T) => string | number | null;
  render?: (row: T) => ReactNode;
  sortable?: boolean;
  widthClassName?: string;
}

type SortDirection = "asc" | "desc";

const ALIGN_CLASSES: Record<"left" | "right" | "center", string> = {
  left: "text-left",
  right: "text-right",
  center: "text-center",
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  emptyMessage = "No data available.",
  defaultSortKey,
  defaultSortDirection = "asc",
}: {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  emptyMessage?: string;
  defaultSortKey?: string;
  defaultSortDirection?: SortDirection;
}) {
  const [sortKey, setSortKey] = useState<string | undefined>(defaultSortKey);
  const [sortDirection, setSortDirection] = useState<SortDirection>(defaultSortDirection);

  const sortedRows = useMemo(() => {
    const column = columns.find((c) => c.key === sortKey);
    if (!column?.accessor) return rows;
    const accessor = column.accessor;
    const sorted = [...rows].sort((a, b) => {
      const av = accessor(a);
      const bv = accessor(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") return av - bv;
      return String(av).localeCompare(String(bv));
    });
    return sortDirection === "asc" ? sorted : sorted.reverse();
  }, [rows, columns, sortKey, sortDirection]);

  function toggleSort(column: DataTableColumn<T>) {
    if (!column.sortable || !column.accessor) return;
    if (sortKey === column.key) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(column.key);
      setSortDirection("asc");
    }
  }

  if (loading) {
    return (
      <div className="overflow-hidden rounded-lg border border-[var(--ric-border)]">
        <div className="animate-pulse divide-y divide-[var(--ric-border)]">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-9 bg-[var(--ric-section-bg)]" />
          ))}
        </div>
      </div>
    );
  }

  if (rows.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--ric-border)]">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="bg-[var(--ric-section-bg)]">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--ric-text-secondary)] ${
                  ALIGN_CLASSES[column.align ?? "left"]
                } ${column.widthClassName ?? ""}`}
              >
                {column.sortable && column.accessor ? (
                  <button
                    type="button"
                    onClick={() => toggleSort(column)}
                    className="inline-flex items-center gap-1 hover:text-[var(--ric-text-primary)]"
                  >
                    {column.header}
                    {sortKey === column.key ? (
                      sortDirection === "asc" ? (
                        <ArrowUp className="h-3 w-3" aria-hidden="true" />
                      ) : (
                        <ArrowDown className="h-3 w-3" aria-hidden="true" />
                      )
                    ) : (
                      <ArrowUpDown className="h-3 w-3 opacity-40" aria-hidden="true" />
                    )}
                  </button>
                ) : (
                  column.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--ric-border)]">
          {sortedRows.map((row) => (
            <tr key={rowKey(row)} className="hover:bg-[var(--ric-section-bg)]">
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-3 py-2 text-[var(--ric-text-primary)] ${ALIGN_CLASSES[column.align ?? "left"]}`}
                >
                  {column.render ? column.render(row) : (column.accessor?.(row) ?? "--")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
