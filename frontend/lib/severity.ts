/**
 * Severity vocabulary ported from dashboard/ui_components.py::SEVERITY_LABELS
 * so every severity value renders identically to the existing Streamlit
 * dashboard across the five agents and the orchestrator -- not a
 * reinvented taxonomy.
 */

export const SEVERITY_LABELS: Record<string, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  unable_to_assess: "Unable to assess",
  not_applicable: "Not applicable",
  insufficient: "Insufficient",
  sufficient: "Sufficient",
  cannot_determine: "Cannot determine",
  // Returned by InventoryRiskEngine for SKUs with no sales velocity to
  // assess yet -- distinct from unable_to_assess (an agent-level failure).
  unknown: "Unknown (no velocity data)",
};

interface SeverityStyle {
  bg: string;
  text: string;
  dot: string;
}

const SEVERITY_STYLES: Record<string, SeverityStyle> = {
  critical: { bg: "bg-red-50", text: "text-red-700", dot: "bg-red-500" },
  high: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-500" },
  insufficient: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-500" },
  medium: { bg: "bg-yellow-50", text: "text-yellow-800", dot: "bg-yellow-500" },
  low: { bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-500" },
  sufficient: { bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-500" },
  unable_to_assess: { bg: "bg-slate-100", text: "text-slate-600", dot: "bg-slate-400" },
  cannot_determine: { bg: "bg-slate-100", text: "text-slate-600", dot: "bg-slate-400" },
  not_applicable: { bg: "bg-slate-100", text: "text-slate-500", dot: "bg-slate-300" },
  unknown: { bg: "bg-slate-100", text: "text-slate-500", dot: "bg-slate-300" },
};

const DEFAULT_STYLE: SeverityStyle = SEVERITY_STYLES.unable_to_assess;

// Literal hex equivalents of the --ric-severity-* tokens in globals.css,
// for contexts (chart fills) that can't consume a Tailwind class name.
const SEVERITY_HEX: Record<string, string> = {
  critical: "#d32f2f",
  high: "#f57c00",
  insufficient: "#f57c00",
  medium: "#b58900",
  low: "#2e7d32",
  sufficient: "#2e7d32",
  unable_to_assess: "#94a3b8",
  cannot_determine: "#94a3b8",
  not_applicable: "#cbd5e1",
  unknown: "#cbd5e1",
};

// Preferred display order for a severity-keyed breakdown (e.g. a chart or
// table of risk_level_counts) -- most severe first, with any unmapped key
// (there shouldn't be one, but never silently drop data) appended last.
export const SEVERITY_DISPLAY_ORDER = [
  "critical",
  "high",
  "insufficient",
  "medium",
  "low",
  "sufficient",
  "unable_to_assess",
  "cannot_determine",
  "not_applicable",
  "unknown",
];

export function orderSeverityKeys(keys: string[]): string[] {
  return [...keys].sort((a, b) => {
    const ai = SEVERITY_DISPLAY_ORDER.indexOf(a);
    const bi = SEVERITY_DISPLAY_ORDER.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });
}

const DEFAULT_HEX = SEVERITY_HEX.unable_to_assess;

export function severityLabel(value?: string | null): string {
  if (!value) return "Unknown";
  return SEVERITY_LABELS[value] ?? value;
}

export function severityStyle(value?: string | null): SeverityStyle {
  if (!value) return DEFAULT_STYLE;
  return SEVERITY_STYLES[value] ?? DEFAULT_STYLE;
}

export function severityHex(value?: string | null): string {
  if (!value) return DEFAULT_HEX;
  return SEVERITY_HEX[value] ?? DEFAULT_HEX;
}
