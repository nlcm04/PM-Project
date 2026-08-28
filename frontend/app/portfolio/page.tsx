"use client";

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/Card";
import { HealthChart } from "@/components/portfolio/HealthChart";
import { FactorExposureChart } from "@/components/portfolio/FactorExposureChart";
import { HoldingsTable } from "@/components/portfolio/HoldingsTable";
import { PortfolioEditor } from "@/components/portfolio/PortfolioEditor";
import { SnapshotMetaBanner } from "@/components/ui/SnapshotMetaBanner";
import { usePortfolio } from "@/lib/usePortfolio";
import { useAutoRefresh } from "@/lib/useAutoRefresh";
import {
  computeHistoryMaxDrawdown,
  computeHistorySharpe,
  computeHoldings,
  computeNav,
  loadNavHistory,
  recordNavHistoryPoint,
  type NavHistoryPoint,
} from "@/lib/portfolio";
import {
  DATA_MODE,
  getHoldings,
  getPerformanceHealth,
  getRankings,
  type Holding,
  type PerformanceSnapshot,
  type RankedStock,
} from "@/lib/api";

export default function PortfolioPage() {
  const { portfolio, setPortfolio, hydrated } = usePortfolio();
  const [snapshots, setSnapshots] = useState<PerformanceSnapshot[]>([]);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [rankings, setRankings] = useState<RankedStock[]>([]);
  const [navHistory, setNavHistory] = useState<NavHistoryPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useAutoRefresh(() => {
    Promise.all([getPerformanceHealth(), getHoldings(), getRankings()])
      .then(([s, h, r]) => {
        setSnapshots(s);
        setHoldings(h);
        setRankings(r);
        setError(null);
      })
      .catch((e) => setError(String(e)));
  });

  const priceByTicker = useMemo(() => {
    const map = new Map<string, number>();
    for (const r of rankings) if (r.last_price != null) map.set(r.ticker.toUpperCase(), r.last_price);
    return map;
  }, [rankings]);

  const computedHoldings = useMemo(() => computeHoldings(portfolio, priceByTicker), [portfolio, priceByTicker]);
  const userNav = useMemo(() => computeNav(portfolio, computedHoldings), [portfolio, computedHoldings]);
  const hasUserPortfolio = portfolio.cash > 0 || portfolio.holdings.length > 0;

  useEffect(() => {
    if (!hydrated) return;
    if (!hasUserPortfolio) {
      setNavHistory(loadNavHistory());
      return;
    }
    setNavHistory(recordNavHistoryPoint(userNav));
  }, [hydrated, hasUserPortfolio, userNav]);

  const latestBacktest = snapshots.at(-1);
  const userSharpe = computeHistorySharpe(navHistory);
  const userDrawdown = computeHistoryMaxDrawdown(navHistory);

  const totalUnrealizedPnl = computedHoldings.reduce((sum, h) => sum + h.unrealizedPnlNet, 0);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-cream">Portfolio Health</h1>
        <p className="mt-1 text-sm text-cream/60">Enter your own NAV, cash, and holdings to track them here.</p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          Could not reach the backend API ({error}). Is FastAPI running on NEXT_PUBLIC_API_BASE_URL?
        </div>
      )}

      <SnapshotMetaBanner />

      <PortfolioEditor portfolio={portfolio} computedHoldings={computedHoldings} onChange={setPortfolio} />

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <div className="text-xs text-cream/50">NAV</div>
          <div className="mt-1 text-2xl font-bold text-cream">
            {hasUserPortfolio
              ? Math.round(userNav).toLocaleString()
              : latestBacktest
                ? Math.round(latestBacktest.nav).toLocaleString()
                : "—"}
          </div>
          {hasUserPortfolio && (
            <div className={`mt-0.5 text-xs ${totalUnrealizedPnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {totalUnrealizedPnl >= 0 ? "+" : ""}
              {Math.round(totalUnrealizedPnl).toLocaleString()} unrealized
            </div>
          )}
        </Card>
        <Card>
          <div className="text-xs text-cream/50">Sharpe Ratio</div>
          <div className="mt-1 text-2xl font-bold text-amber-400">
            {hasUserPortfolio
              ? (userSharpe?.toFixed(2) ?? "—")
              : (latestBacktest?.sharpe_ratio?.toFixed(2) ?? "—")}
          </div>
          {hasUserPortfolio && userSharpe == null && (
            <div className="mt-0.5 text-xs text-cream/40">needs a few more days of history</div>
          )}
        </Card>
        <Card>
          <div className="text-xs text-cream/50">Max Drawdown</div>
          <div className="mt-1 text-2xl font-bold text-red-300">
            {hasUserPortfolio
              ? userDrawdown != null
                ? `${(userDrawdown * 100).toFixed(1)}%`
                : "—"
              : latestBacktest
                ? `${(latestBacktest.max_drawdown * 100).toFixed(1)}%`
                : "—"}
          </div>
        </Card>
      </div>

      <Card>
        <h2 className="mb-1 text-base font-semibold text-cream">Equity Curve</h2>
        <p className="mb-3 text-xs text-cream/50">
          {hasUserPortfolio
            ? "Your own NAV, recorded once per day you visit this page (client-side only)."
            : "No portfolio entered yet -- showing the backtested shortlist basket instead."}
        </p>
        {hasUserPortfolio && navHistory.length > 1 ? (
          <HealthChart snapshots={navHistory.map((p) => ({ snapshot_date: p.date, nav: p.nav }))} />
        ) : !hasUserPortfolio && snapshots.length > 0 ? (
          <HealthChart snapshots={snapshots} />
        ) : (
          <p className="text-sm text-cream/50">
            {hasUserPortfolio ? "Come back tomorrow to start seeing a curve." : "No performance snapshots yet."}
          </p>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-base font-semibold text-cream">Shortlist Factor Exposure</h2>
        <p className="mb-3 text-xs text-cream/50">
          Average factor z-scores of today&rsquo;s optimizer shortlist, not your personal holdings.
        </p>
        <FactorExposureChart exposures={latestBacktest?.factor_exposures ?? {}} />
      </Card>

      {DATA_MODE !== "static" && (
        <Card>
          <h2 className="mb-3 text-base font-semibold text-cream">Approved-Pick Holdings</h2>
          <p className="mb-3 text-xs text-cream/50">
            Holdings opened by approving a Daily Discovery pick against a live backend -- separate from
            the portfolio you enter above.
          </p>
          <HoldingsTable holdings={holdings} />
        </Card>
      )}
    </div>
  );
}
