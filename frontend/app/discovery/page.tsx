"use client";

import { useEffect, useState } from "react";
import { RankingsTable } from "@/components/discovery/RankingsTable";
import { ShortlistSummary } from "@/components/discovery/ShortlistSummary";
import { FlowAlertPanel } from "@/components/discovery/FlowAlertPanel";
import { SnapshotMetaBanner } from "@/components/ui/SnapshotMetaBanner";
import { getFlowAlerts, getPicks, getRankings, type DailyStockPick, type FlowAlert, type RankedStock } from "@/lib/api";

export default function DiscoveryPage() {
  const [rankings, setRankings] = useState<RankedStock[] | null>(null);
  const [picks, setPicks] = useState<DailyStockPick[]>([]);
  const [flowAlerts, setFlowAlerts] = useState<FlowAlert[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getRankings(), getPicks(), getFlowAlerts()])
      .then(([r, p, alerts]) => {
        setRankings(r);
        setPicks(p);
        setFlowAlerts(alerts);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const pickTickers = new Set(picks.map((p) => p.ticker));

  return (
    <div className="mx-auto max-w-7xl">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-cream">Daily Discovery</h1>
        <p className="mt-1 text-sm text-cream/60">
          Every tracked HOSE ticker, ranked best to worst across value, quality, and volume signals.
          Nothing here is ever auto-invested &mdash; add positions yourself on the Portfolio page.
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          Could not reach the backend API ({error}). Is FastAPI running on NEXT_PUBLIC_API_BASE_URL?
        </div>
      )}

      <SnapshotMetaBanner />

      <div className="mb-8">
        <FlowAlertPanel alerts={flowAlerts} />
      </div>

      <ShortlistSummary picks={picks} />

      {rankings === null && !error ? (
        <p className="text-cream/50">Loading rankings&hellip;</p>
      ) : (
        <RankingsTable rows={rankings ?? []} pickTickers={pickTickers} />
      )}
    </div>
  );
}
