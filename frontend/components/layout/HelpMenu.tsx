"use client";

/**
 * Real, honest help content about what this demo actually is and does --
 * not a stub linking to a support system that doesn't exist.
 */

import { useRef, useState } from "react";
import { HelpCircle } from "lucide-react";

import { useDismiss } from "@/lib/useDismiss";

export function HelpMenu() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  useDismiss(containerRef, open, () => setOpen(false));

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="Help"
        aria-expanded={open}
        className="rounded-lg p-2 text-[var(--ric-text-secondary)] hover:bg-[var(--ric-page-bg)]"
      >
        <HelpCircle className="h-4.5 w-4.5" aria-hidden="true" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-72 rounded-lg border border-[var(--ric-border)] bg-[var(--ric-card-bg)] p-3 text-sm shadow-lg">
          <p className="font-medium text-[var(--ric-text-primary)]">About this demo</p>
          <p className="mt-1 text-[var(--ric-text-secondary)]">
            Retail Intelligence Cloud is a read-only view over a fixed, synthetic 90-day retail dataset. No
            order, inventory, or customer record is ever changed by this UI -- every recommendation requires
            human approval elsewhere.
          </p>
          <p className="mt-3 font-medium text-[var(--ric-text-primary)]">Try asking Retail AI</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[var(--ric-text-secondary)]">
            <li>&quot;Give me today&apos;s retail risk summary.&quot;</li>
            <li>&quot;Which stores are at risk of stockouts this week?&quot;</li>
            <li>&quot;Which orders need immediate attention?&quot;</li>
          </ul>
        </div>
      )}
    </div>
  );
}
