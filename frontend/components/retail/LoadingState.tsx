export function LoadingState({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex items-center gap-2 py-6 text-sm text-[var(--ric-text-secondary)]">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[var(--ric-border)] border-t-[var(--ric-primary)]" />
      <span>{message}</span>
    </div>
  );
}
