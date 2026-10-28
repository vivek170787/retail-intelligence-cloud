"use client";

/**
 * Real, honestly-scoped global search: it searches the app's own known
 * navigation destinations (workspace names), not orders/SKUs/customers --
 * there is no backend search endpoint for that, so this never pretends
 * to offer it. Selecting a disabled destination still navigates there;
 * that page's own "Coming soon" card explains its status.
 */

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

import { NAV_GROUPS } from "@/components/layout/nav-config";

const ALL_ITEMS = NAV_GROUPS.flatMap((group) =>
  group.items.map((item) => ({ label: item.label, href: item.href, group: group.title, enabled: item.enabled }))
);

export function GlobalSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return ALL_ITEMS.filter((item) => item.label.toLowerCase().includes(q)).slice(0, 8);
  }, [query]);

  function goTo(href: string) {
    router.push(href);
    setQuery("");
    setOpen(false);
  }

  return (
    <div className="relative hidden max-w-sm flex-1 sm:block">
      <Search
        className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--ric-text-secondary)]"
        aria-hidden="true"
      />
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        placeholder="Search workspaces..."
        aria-label="Search workspaces"
        className="w-full rounded-lg border border-[var(--ric-border)] bg-[var(--ric-page-bg)] py-1.5 pl-8 pr-3 text-sm text-[var(--ric-text-primary)] outline-none focus:border-[var(--ric-primary)]"
      />
      {open && query.trim() && (
        <ul className="absolute left-0 right-0 top-full z-50 mt-1 max-h-72 overflow-y-auto rounded-lg border border-[var(--ric-border)] bg-[var(--ric-card-bg)] shadow-lg">
          {results.length > 0 ? (
            results.map((item) => (
              <li key={item.href}>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => goTo(item.href)}
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-[var(--ric-page-bg)]"
                >
                  <span className="text-[var(--ric-text-primary)]">{item.label}</span>
                  <span className="text-xs text-[var(--ric-text-secondary)]">
                    {item.group}
                    {!item.enabled ? " -- coming soon" : ""}
                  </span>
                </button>
              </li>
            ))
          ) : (
            <li className="px-3 py-2 text-sm text-[var(--ric-text-secondary)]">No matching workspace or page.</li>
          )}
        </ul>
      )}
    </div>
  );
}
