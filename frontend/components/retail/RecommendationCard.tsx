/**
 * One recommended action requiring human review. The "Mark reviewed"
 * affordance (ReviewActionButton) is session-only and local -- see that
 * component's comment for why.
 */

import { ClipboardList } from "lucide-react";

import { ReviewActionButton } from "@/components/retail/ReviewActionButton";

export function RecommendationCard({ action, count }: { action: string; count: number }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-[var(--ric-border)] bg-[var(--ric-card-bg)] p-3">
      <div className="flex items-start gap-2.5">
        <ClipboardList className="mt-0.5 h-4 w-4 shrink-0 text-[var(--ric-text-secondary)]" aria-hidden="true" />
        <div>
          <p className="text-sm text-[var(--ric-text-primary)]">{action}</p>
          <p className="mt-0.5 text-xs text-[var(--ric-text-secondary)]">{count} order(s) affected</p>
        </div>
      </div>
      <div className="shrink-0">
        <ReviewActionButton itemLabel={action} />
      </div>
    </div>
  );
}
