/**
 * Lowest-level pill primitive -- no domain knowledge of severity, risk,
 * or order status. StatusBadge and the severity-aware risk indicator
 * (components/retail/SeverityBadge.tsx, backed by lib/severity.ts) are
 * both built on top of this.
 */

export type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger";

const TONE_CLASSES: Record<BadgeTone, { bg: string; text: string; dot: string }> = {
  neutral: { bg: "bg-slate-100", text: "text-slate-600", dot: "bg-slate-400" },
  info: { bg: "bg-blue-50", text: "text-blue-700", dot: "bg-blue-500" },
  success: { bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-500" },
  warning: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-500" },
  danger: { bg: "bg-red-50", text: "text-red-700", dot: "bg-red-500" },
};

export interface BadgeColors {
  bg: string;
  text: string;
  dot: string;
}

export function Badge({
  label,
  tone = "neutral",
  dot = false,
  colors,
}: {
  label: string;
  tone?: BadgeTone;
  dot?: boolean;
  /** Overrides `tone` with an explicit palette -- used by callers with a
   * finer-grained vocabulary than the five generic tones (e.g. the
   * severity scale's distinct medium-vs-high colors). */
  colors?: BadgeColors;
}) {
  const palette = colors ?? TONE_CLASSES[tone];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${palette.bg} ${palette.text}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${palette.dot}`} aria-hidden="true" />}
      {label}
    </span>
  );
}
