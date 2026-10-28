import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border border-[var(--ric-border)] bg-[var(--ric-card-bg)] shadow-sm transition-shadow duration-150 hover:shadow-md ${className}`}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="border-b border-[var(--ric-border)] px-5 py-3.5">
      <h2 className="text-sm font-semibold text-[var(--ric-text-primary)]">{title}</h2>
      {subtitle && <p className="mt-0.5 text-xs text-[var(--ric-text-secondary)]">{subtitle}</p>}
    </div>
  );
}

export function CardBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`px-5 py-4 ${className}`}>{children}</div>;
}
