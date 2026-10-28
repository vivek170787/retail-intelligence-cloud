import { CalendarClock } from "lucide-react";

export function DataFreshnessNote({ note }: { note: string }) {
  return (
    <p className="flex items-center gap-1.5 text-xs text-[var(--ric-text-secondary)]">
      <CalendarClock className="h-3.5 w-3.5" aria-hidden="true" />
      {note}
    </p>
  );
}
