import { Badge, type BadgeTone } from "@/components/ui/Badge";

/**
 * For statuses that are NOT the five-agent severity vocabulary (that's
 * SeverityBadge/RiskIndicator) -- e.g. an agent name consulted, a generic
 * "healthy"/"unavailable" state. Tone is inferred from a small explicit
 * map rather than guessed, and unknown values fall back to neutral
 * (never invents a meaning for a status this project doesn't define).
 */

const STATUS_TONE_MAP: Record<string, BadgeTone> = {
  healthy: "success",
  available: "success",
  ok: "success",
  unavailable: "danger",
  failed: "danger",
  error: "danger",
  degraded: "warning",
};

export function StatusBadge({ label }: { label: string }) {
  const tone = STATUS_TONE_MAP[label.toLowerCase()] ?? "neutral";
  return <Badge label={label} tone={tone} dot />;
}
