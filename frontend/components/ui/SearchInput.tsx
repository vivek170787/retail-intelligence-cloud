import { Search } from "lucide-react";

/**
 * Generic search/filter text input. Not yet wired to any live page in
 * this increment (no row-level filterable table exists on a wired-up
 * workspace yet) -- available for the operational workspaces planned
 * next (Inventory, Promotions, Order Fulfillment, Customer Experience).
 */
export function SearchInput({
  value,
  onChange,
  placeholder = "Search...",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="relative">
      <Search
        className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--ric-text-secondary)]"
        aria-hidden="true"
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-[var(--ric-border)] bg-[var(--ric-card-bg)] py-1.5 pl-8 pr-3 text-sm text-[var(--ric-text-primary)] outline-none transition-colors focus:border-[var(--ric-primary)] focus:ring-2 focus:ring-[var(--ric-accent-light)]"
      />
    </div>
  );
}
