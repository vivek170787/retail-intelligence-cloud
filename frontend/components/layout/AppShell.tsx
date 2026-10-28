"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { Sidebar } from "@/components/layout/Sidebar";
import { TopNav } from "@/components/layout/TopNav";

const COLLAPSE_STORAGE_KEY = "ric_sidebar_collapsed";

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Restore the user's collapse preference after mount, deferred to a
  // microtask (not called synchronously in the effect body, and not read
  // during SSR) -- avoids a hydration mismatch at the cost of a harmless
  // one-frame flash for users who previously collapsed the sidebar.
  useEffect(() => {
    if (typeof window === "undefined") return;
    Promise.resolve().then(() => {
      setCollapsed(window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === "1");
    });
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(COLLAPSE_STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  return (
    <div className="flex h-screen flex-col">
      <TopNav onToggleMobileNav={() => setMobileNavOpen((o) => !o)} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          collapsed={collapsed}
          onToggleCollapsed={toggleCollapsed}
          mobileOpen={mobileNavOpen}
          onCloseMobile={() => setMobileNavOpen(false)}
        />
        <main className="flex-1 overflow-y-auto bg-[var(--ric-page-bg)] p-6">{children}</main>
      </div>
    </div>
  );
}
