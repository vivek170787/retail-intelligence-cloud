"use client";

/**
 * Session-only, local "mark reviewed" affordance. There is no backend
 * endpoint to persist a review decision -- every agent in this system is
 * read-only -- so this never pretends to write anything back; the label
 * and confirmation dialog say so explicitly. Shared by RecommendationCard
 * and the Recommended Actions table so both offer identical, honest
 * behavior rather than two subtly different ones.
 */

import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog";

export function ReviewActionButton({ itemLabel }: { itemLabel: string }) {
  const [reviewed, setReviewed] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);

  if (reviewed) {
    return <Badge label="Reviewed (this session)" tone="success" dot />;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setDialogOpen(true)}
        className="rounded-md border border-[var(--ric-border)] px-2.5 py-1 text-xs font-medium text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
      >
        Mark reviewed
      </button>
      <ConfirmationDialog
        open={dialogOpen}
        title="Mark this action as reviewed?"
        description={`This only updates your current browser session for "${itemLabel}" -- it is not saved anywhere, and no order, inventory, or customer record is changed.`}
        confirmLabel="Mark reviewed"
        onConfirm={() => {
          setReviewed(true);
          setDialogOpen(false);
        }}
        onCancel={() => setDialogOpen(false)}
      />
    </>
  );
}
