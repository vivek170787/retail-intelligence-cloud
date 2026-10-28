import { severityLabel, severityStyle } from "@/lib/severity";
import { Badge } from "@/components/ui/Badge";

/**
 * This IS the design system's "risk indicator" component -- severity-aware
 * (critical/high/medium/low/unable_to_assess/not_applicable/insufficient/
 * sufficient/cannot_determine), rendered through the generic Badge
 * primitive with its own finer-grained color palette (lib/severity.ts)
 * since the severity scale needs more distinct colors than Badge's five
 * generic tones (e.g. medium vs. high). Kept under its original name
 * (not renamed to RiskIndicator) so every existing import keeps working.
 */
export function SeverityBadge({ value }: { value?: string | null }) {
  return <Badge label={severityLabel(value)} colors={severityStyle(value)} dot />;
}
