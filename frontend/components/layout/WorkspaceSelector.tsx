import { Layers } from "lucide-react";

/**
 * Honest placeholder: this demo has exactly one synthetic dataset/
 * workspace. A real multi-workspace switcher would imply a capability
 * (multi-tenant data isolation) this project doesn't have, so this stays
 * a clearly disabled control rather than a fake-functional dropdown.
 */
export function WorkspaceSelector() {
  return (
    <button
      type="button"
      disabled
      title="This demo has a single synthetic workspace -- multi-workspace switching is not implemented."
      className="hidden items-center gap-1.5 rounded-md border border-[var(--ric-border)] px-3 py-1.5 text-sm text-[var(--ric-text-secondary)] disabled:cursor-not-allowed lg:flex"
    >
      <Layers className="h-3.5 w-3.5" aria-hidden="true" />
      <span>Synthetic Demo Workspace</span>
    </button>
  );
}
