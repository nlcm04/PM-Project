"use client";

import { useEffect, useRef } from "react";

const DEFAULT_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

/** Runs `callback` immediately, then again on a fixed interval, and again
 * whenever the tab regains visibility (so switching back to a tab you left
 * open shows fresh data right away instead of waiting for the next tick).
 *
 * The underlying data here only actually changes about once an hour (the
 * GitHub Pages snapshot's own refresh cadence), so this doesn't poll faster
 * than that -- it just means an open tab doesn't need a manual reload to
 * pick up the next hourly refresh once it's published.
 *
 * Uses a ref for the callback so passing a fresh inline function on every
 * render doesn't tear down and restart the interval each time.
 */
export function useAutoRefresh(callback: () => void, intervalMs: number = DEFAULT_INTERVAL_MS): void {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    callbackRef.current();
    const interval = setInterval(() => callbackRef.current(), intervalMs);

    function handleVisibility() {
      if (document.visibilityState === "visible") callbackRef.current();
    }
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [intervalMs]);
}
