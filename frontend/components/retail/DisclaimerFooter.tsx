export function DisclaimerFooter({ text }: { text?: string }) {
  return (
    <p className="mt-6 text-xs text-[var(--ric-text-secondary)]">
      {text ??
        "All recommendations are read-only and require human approval. No order, inventory, or customer record is modified by this application."}
    </p>
  );
}
