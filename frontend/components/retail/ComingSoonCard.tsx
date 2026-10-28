import { Construction } from "lucide-react";

/**
 * Honest placeholder for a sidebar destination with no wired-up workspace
 * yet. Never fabricates data, metrics, or integration status -- states
 * plainly what exists today (e.g. "backend ready") and what doesn't.
 */
export function ComingSoonCard({ title, note }: { title: string; note: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-6 py-16 text-center">
      <Construction className="h-8 w-8 text-[var(--ric-text-secondary)]" aria-hidden="true" />
      <h1 className="mt-4 text-lg font-semibold text-[var(--ric-text-primary)]">{title}</h1>
      <p className="mt-2 max-w-md text-sm text-[var(--ric-text-secondary)]">{note}</p>
      <span className="mt-4 inline-flex items-center rounded-full bg-[var(--ric-page-bg)] px-3 py-1 text-xs font-medium text-[var(--ric-text-secondary)]">
        Coming soon
      </span>
    </div>
  );
}
