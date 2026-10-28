import type { ReactNode } from "react";

/**
 * Horizontal container for filter controls (SelectFilter, SearchInput,
 * etc.) above a table or chart, with consistent spacing/alignment.
 */
export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-4 border-b border-[var(--ric-border)] px-5 py-3">{children}</div>;
}
