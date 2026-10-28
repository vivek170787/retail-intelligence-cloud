"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Lock, PanelLeftClose, PanelLeftOpen, X } from "lucide-react";

import { NAV_GROUPS, type NavGroup } from "@/components/layout/nav-config";

function NavGroups({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <>
      {NAV_GROUPS.map((group: NavGroup) => (
        <div key={group.title} className="mb-5">
          {!collapsed && (
            <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wide text-[var(--ric-text-secondary)]">
              {group.title}
            </p>
          )}
          {collapsed && <div className="mx-3 mb-2 border-t border-[var(--ric-border)]" />}
          <ul className="space-y-0.5">
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;

              if (!item.enabled) {
                return (
                  <li key={item.href}>
                    <span
                      title={item.comingSoonNote ?? "Coming soon"}
                      className={`flex cursor-not-allowed items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-[var(--ric-text-secondary)] opacity-60 ${
                        collapsed ? "justify-center" : ""
                      }`}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      {!collapsed && (
                        <>
                          <span className="flex-1">{item.label}</span>
                          <Lock className="h-3 w-3" aria-hidden="true" />
                        </>
                      )}
                    </span>
                  </li>
                );
              }

              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    title={collapsed ? item.label : undefined}
                    onClick={onNavigate}
                    className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                      collapsed ? "justify-center" : ""
                    } ${
                      isActive
                        ? "bg-[var(--ric-accent-light)] font-medium text-[var(--ric-primary)]"
                        : "text-[var(--ric-text-primary)] hover:bg-[var(--ric-section-bg)]"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    {!collapsed && <span>{item.label}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </>
  );
}

export function Sidebar({
  collapsed,
  onToggleCollapsed,
  mobileOpen,
  onCloseMobile,
}: {
  collapsed: boolean;
  onToggleCollapsed: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  return (
    <>
      {/* Desktop: persistent, collapsible icon-rail sidebar. */}
      <aside
        className={`hidden shrink-0 flex-col border-r border-[var(--ric-border)] bg-[var(--ric-card-bg)] transition-[width] duration-150 md:flex ${
          collapsed ? "w-16" : "w-64"
        }`}
      >
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          <NavGroups collapsed={collapsed} />
        </nav>
        <div className="border-t border-[var(--ric-border)] p-2">
          <button
            type="button"
            onClick={onToggleCollapsed}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm text-[var(--ric-text-secondary)] hover:bg-[var(--ric-page-bg)]"
          >
            {collapsed ? (
              <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
            ) : (
              <>
                <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* Mobile: slide-over drawer, only rendered when opened via the TopNav hamburger. */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={onCloseMobile} aria-hidden="true" />
          <aside className="relative z-50 flex h-full w-72 flex-col bg-[var(--ric-card-bg)] shadow-lg">
            <div className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--ric-border)] px-4">
              <span className="text-sm font-semibold text-[var(--ric-text-primary)]">Navigation</span>
              <button
                type="button"
                onClick={onCloseMobile}
                title="Close navigation"
                className="rounded-lg p-1.5 text-[var(--ric-text-secondary)] hover:bg-[var(--ric-page-bg)]"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto px-3 py-4">
              <NavGroups collapsed={false} onNavigate={onCloseMobile} />
            </nav>
          </aside>
        </div>
      )}
    </>
  );
}
