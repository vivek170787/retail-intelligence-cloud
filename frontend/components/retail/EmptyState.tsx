import { Info } from "lucide-react";

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md bg-[var(--ric-page-bg)] px-3 py-2.5 text-sm text-[var(--ric-text-secondary)]">
      <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
