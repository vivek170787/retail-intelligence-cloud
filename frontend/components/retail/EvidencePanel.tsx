export function EvidencePanel({ evidence }: { evidence: unknown }) {
  return (
    <details className="rounded-md border border-[var(--ric-border)]">
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-[var(--ric-text-primary)]">
        Supporting evidence (raw)
      </summary>
      <pre className="max-h-96 overflow-auto bg-[var(--ric-page-bg)] px-3 py-2 text-xs text-[var(--ric-text-secondary)]">
        {JSON.stringify(evidence, null, 2)}
      </pre>
    </details>
  );
}
