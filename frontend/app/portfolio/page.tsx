"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { HealthChart } from "@/components/portfolio/HealthChart";
import { FactorExposureChart } from "@/components/portfolio/FactorExposureChart";
import { HoldingsTable } from "@/components/portfolio/HoldingsTable";
import { getHoldings, getPerformanceHealth, type Holding, type PerformanceSnapshot } from "@/lib/api";

export default function PortfolioPage() {
  const [snapshots, setSnapshots] = useState<PerformanceSnapshot[]>([]);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getPerformanceHealth(), getHoldings()])
      .then(([s, h]) => {
        setSnapshots(s);
        setHoldings(h);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const latest = snapshots.at(-1);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-cream">Portfolio Health</h1>
        <p className="mt-1 text-sm text-cream/60">NAV, drawdown, factor exposure, and current holdings.</p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          Could not reach the backend API ({error}). Is FastAPI running on NEXT_PUBLIC_API_BASE_URL?
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <div className="text-xs text-cream/50">NAV</div>
          <div className="mt-1 text-2xl font-bold text-cream">{latest ? latest.nav.toLocaleString() : "—"}</div>
        </Card>
        <Card>
          <div className="text-xs text-cream/50">Sharpe Ratio</div>
          <div className="mt-1 text-2xl font-bold text-amber-400">{latest ? latest.sharpe_ratio.toFixed(2) : "—"}</div>
        </Card>
        <Card>
          <div className="text-xs text-cream/50">Max Drawdown</div>
          <div className="mt-1 text-2xl font-bold text-red-300">
            {latest ? `${(latest.max_drawdown * 100).toFixed(1)}%` : "—"}
          </div>
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 text-base font-semibold text-cream">Equity Curve</h2>
        {snapshots.length > 0 ? (
          <HealthChart snapshots={snapshots} />
        ) : (
          <p className="text-sm text-cream/50">No performance snapshots yet.</p>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-base font-semibold text-cream">Factor Exposure</h2>
        <FactorExposureChart exposures={latest?.factor_exposures ?? {}} />
      </Card>

      <Card>
        <h2 className="mb-3 text-base font-semibold text-cream">Holdings</h2>
        <HoldingsTable holdings={holdings} />
      </Card>
    </div>
  );
}
