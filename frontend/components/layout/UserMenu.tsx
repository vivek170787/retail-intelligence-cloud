"use client";

/**
 * Cosmetic user menu -- this project has no real authentication system,
 * so "Sign out" stays visibly disabled. "Preferences" is a real link to
 * the (currently placeholder) /settings page, since that destination
 * genuinely exists.
 */

import { useRef, useState } from "react";
import Link from "next/link";
import { LogOut, Settings } from "lucide-react";

import { useDismiss } from "@/lib/useDismiss";

export function UserMenu() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  useDismiss(containerRef, open, () => setOpen(false));

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="Demo User (not a real signed-in session)"
        aria-expanded={open}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--ric-primary)] text-xs font-medium text-white"
      >
        RA
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-56 rounded-md border border-[var(--ric-border)] bg-[var(--ric-card-bg)] py-1 text-sm shadow-lg">
          <div className="border-b border-[var(--ric-border)] px-3 py-2">
            <p className="font-medium text-[var(--ric-text-primary)]">Demo User</p>
            <p className="text-xs text-[var(--ric-text-secondary)]">Not a real signed-in session</p>
          </div>
          <Link
            href="/settings"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-3 py-2 text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
          >
            <Settings className="h-3.5 w-3.5" aria-hidden="true" />
            Preferences
          </Link>
          <button
            type="button"
            disabled
            title="No real authentication in this demo"
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-[var(--ric-text-secondary)] disabled:cursor-not-allowed"
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
