import type { ReactNode } from "react";

/**
 * Turns an arbitrary (and per-category differently-shaped) evidence
 * object into a plain-English, nested bullet list instead of a raw
 * JSON dump -- every field name is humanized and every value is
 * formatted for reading, but nothing here invents or recomputes a
 * number: it only presents what the agent already put in `evidence`.
 */

const _ACRONYMS: Record<string, string> = {
  sku: "SKU",
  skus: "SKUs",
  id: "ID",
  ids: "IDs",
  cx: "Customer Experience",
};

function humanizeKey(key: string): string {
  return key
    .split("_")
    .map((word) => _ACRONYMS[word.toLowerCase()] ?? word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatPrimitive(value: string | number | boolean): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return value.toLocaleString();
  return value;
}

function renderValue(value: unknown, depth: number): ReactNode {
  if (value === null || value === undefined) {
    return <span className="italic text-[var(--ric-text-secondary)]">not available</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="italic text-[var(--ric-text-secondary)]">none</span>;
    }
    const allPrimitive = value.every((v) => v === null || typeof v !== "object");
    if (allPrimitive) {
      return <span>{value.map((v) => (v === null ? "none" : formatPrimitive(v as string | number | boolean))).join(", ")}</span>;
    }
    return (
      <ul className="list-disc space-y-1 pl-5">
        {value.map((item, i) => (
          <li key={i}>{renderValue(item, depth + 1)}</li>
        ))}
      </ul>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return <span className="italic text-[var(--ric-text-secondary)]">no details recorded</span>;
    }
    return (
      <ul className={depth === 0 ? "space-y-1.5" : "list-disc space-y-1 pl-5"}>
        {entries.map(([k, v]) => {
          const isNested = (typeof v === "object" && v !== null) && !(Array.isArray(v) && v.every((x) => typeof x !== "object" || x === null));
          return (
            <li key={k}>
              <span className="font-medium text-[var(--ric-text-primary)]">{humanizeKey(k)}:</span>
              {isNested ? <div className="mt-1">{renderValue(v, depth + 1)}</div> : <> {renderValue(v, depth + 1)}</>}
            </li>
          );
        })}
      </ul>
    );
  }

  return <span>{formatPrimitive(value as string | number | boolean)}</span>;
}

export function EvidencePanel({ evidence }: { evidence: unknown }) {
  const hasEvidence =
    evidence !== null && evidence !== undefined && !(typeof evidence === "object" && Object.keys(evidence as object).length === 0);

  return (
    <details className="rounded-lg border border-[var(--ric-border)]">
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-[var(--ric-text-primary)]">
        Supporting evidence
      </summary>
      <div className="max-h-96 overflow-auto px-3 py-2 text-sm text-[var(--ric-text-primary)]">
        {hasEvidence ? (
          renderValue(evidence, 0)
        ) : (
          <span className="italic text-[var(--ric-text-secondary)]">No supporting evidence was recorded for this result.</span>
        )}
      </div>
    </details>
  );
}
