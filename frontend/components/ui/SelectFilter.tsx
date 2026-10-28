/**
 * Generic labeled dropdown filter control. Purely presentational --
 * callers own the selected value and what happens when it changes.
 */

export interface SelectFilterOption {
  value: string;
  label: string;
}

export function SelectFilter({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: SelectFilterOption[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-[var(--ric-text-secondary)]">
      <span className="font-medium text-[var(--ric-text-primary)]">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-[var(--ric-border)] bg-[var(--ric-card-bg)] px-2.5 py-1.5 text-sm text-[var(--ric-text-primary)] outline-none focus:border-[var(--ric-primary)]"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
