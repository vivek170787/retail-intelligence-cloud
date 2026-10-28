"use client";

/**
 * Generic confirmation modal. Purely presentational -- the caller decides
 * what onConfirm actually does (in this project, nothing here ever calls
 * a mutating API; every "confirm" action so far is a local, ephemeral,
 * clearly-labeled UI state change, matching the project's read-only /
 * human-approval-required constraint).
 */

import { useEffect, useRef } from "react";
import { AlertTriangle } from "lucide-react";

export function ConfirmationDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "default",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "default" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const confirmButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    confirmButtonRef.current?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4"
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirmation-dialog-title"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-xl border border-[var(--ric-border)] bg-[var(--ric-card-bg)] p-5 shadow-lg"
      >
        <div className="flex items-start gap-3">
          {tone === "danger" && <AlertTriangle className="h-5 w-5 shrink-0 text-[var(--ric-error)]" aria-hidden="true" />}
          <div>
            <h2 id="confirmation-dialog-title" className="text-sm font-semibold text-[var(--ric-text-primary)]">
              {title}
            </h2>
            <p className="mt-1.5 text-sm text-[var(--ric-text-secondary)]">{description}</p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-[var(--ric-border)] px-3 py-1.5 text-sm font-medium text-[var(--ric-text-primary)] hover:bg-[var(--ric-page-bg)]"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmButtonRef}
            type="button"
            onClick={onConfirm}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium text-white transition-colors ${
              tone === "danger"
                ? "bg-[var(--ric-error)] hover:bg-[#b91c1c]"
                : "bg-[var(--ric-primary)] hover:bg-[var(--ric-primary-hover)]"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
