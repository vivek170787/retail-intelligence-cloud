"use client";

/**
 * Closes an open popover/menu on an outside click or Escape. Deliberately
 * NOT implemented via onBlur -- blurring the trigger button fires before
 * a click on a menu item (e.g. a real <Link>) completes, which can
 * unmount the item mid-click and silently cancel the navigation.
 */

import { useEffect } from "react";
import type { RefObject } from "react";

export function useDismiss(ref: RefObject<HTMLElement | null>, open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;

    function handlePointerDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [ref, open, onClose]);
}
