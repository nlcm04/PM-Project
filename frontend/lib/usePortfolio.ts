"use client";

import { useEffect, useState } from "react";
import { DEFAULT_PORTFOLIO, loadPortfolio, savePortfolio, type PortfolioState } from "./portfolio";

/** Hydration-safe localStorage-backed portfolio state.
 *
 * Static export has no server, but Next still pre-renders each page's HTML
 * shell at build time with no access to the viewer's localStorage. Reading
 * localStorage during the initial render (even on the client, during
 * hydration) would produce different output than that pre-rendered shell
 * and trigger a hydration mismatch. So: render `DEFAULT_PORTFOLIO` on the
 * first pass (matching the static shell exactly), then swap in the real
 * stored value inside `useEffect`, which runs after hydration completes.
 */
export function usePortfolio() {
  const [state, setState] = useState<PortfolioState>(DEFAULT_PORTFOLIO);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setState(loadPortfolio());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) savePortfolio(state);
  }, [state, hydrated]);

  return { portfolio: state, setPortfolio: setState, hydrated };
}
