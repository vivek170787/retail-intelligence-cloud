import type { LucideIcon } from "lucide-react";

export function KpiCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number | string;
  icon?: LucideIcon;
}) {
  return (
    <div className="rounded-lg border border-[var(--ric-border)] bg-[var(--ric-card-bg)] p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-[var(--ric-text-secondary)]">{label}</p>
        {Icon && <Icon className="h-4 w-4 text-[var(--ric-text-secondary)]" aria-hidden="true" />}
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-[var(--ric-text-primary)]">{value}</p>
    </div>
  );
}
