import { Bell, ChevronDown, Menu, ShoppingBag } from "lucide-react";

import { GlobalSearch } from "@/components/layout/GlobalSearch";
import { HelpMenu } from "@/components/layout/HelpMenu";
import { UserMenu } from "@/components/layout/UserMenu";
import { WorkspaceSelector } from "@/components/layout/WorkspaceSelector";

/**
 * Org switcher / notification bell are cosmetic placeholders only -- they
 * do not represent real multi-tenancy or a notification system. This
 * project has no login system either; UserMenu makes that explicit.
 */
export function TopNav({ onToggleMobileNav }: { onToggleMobileNav: () => void }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-4">
      <button
        type="button"
        onClick={onToggleMobileNav}
        title="Open navigation"
        className="rounded-lg p-2 text-[var(--ric-text-secondary)] hover:bg-[var(--ric-page-bg)] md:hidden"
      >
        <Menu className="h-4.5 w-4.5" aria-hidden="true" />
      </button>

      <div className="flex items-center gap-2.5">
        <ShoppingBag className="h-5 w-5 text-[var(--ric-primary)]" aria-hidden="true" />
        <span className="hidden text-[15px] font-semibold text-[var(--ric-text-primary)] sm:inline">
          Retail Intelligence Cloud
        </span>
      </div>

      <GlobalSearch />

      <div className="ml-auto flex items-center gap-2">
        <WorkspaceSelector />

        <button
          type="button"
          disabled
          title="Demonstration UI only -- not a real organization directory"
          className="hidden items-center gap-1.5 rounded-lg border border-[var(--ric-border)] px-3 py-1.5 text-sm text-[var(--ric-text-secondary)] disabled:cursor-not-allowed md:flex"
        >
          <span>Demo Retail Co.</span>
          <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
        </button>

        <HelpMenu />

        <button
          type="button"
          disabled
          title="Demonstration UI only -- no real notification system"
          className="rounded-lg p-2 text-[var(--ric-text-secondary)] disabled:cursor-not-allowed"
        >
          <Bell className="h-4.5 w-4.5" aria-hidden="true" />
        </button>

        <UserMenu />
      </div>
    </header>
  );
}
