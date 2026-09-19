/**
 * Automatic config saving.
 *
 * Enabled by the `ui.auto_save` preference. Every change to the document resets
 * a short timer, so a burst of edits produces one save instead of one per
 * keystroke. The save callback is held in a ref so the timer is not restarted
 * by unrelated re-renders, and it stays off while a save is already in flight
 * so the same document is never submitted twice.
 */

import { useEffect, useRef } from "react";

import type { RevaiConfig } from "@/lib/api";

export function useAutoSave(
  config: RevaiConfig,
  dirty: boolean,
  busy: boolean,
  save: () => void,
  delayMs = 2000,
): void {
  const saveRef = useRef(save);
  useEffect(() => {
    saveRef.current = save;
  }, [save]);

  const enabled = config.ui.auto_save === true;
  useEffect(() => {
    if (!enabled || !dirty || busy) {
      return;
    }
    const timer = setTimeout(() => saveRef.current(), delayMs);
    return () => clearTimeout(timer);
  }, [enabled, dirty, busy, config, delayMs]);
}
