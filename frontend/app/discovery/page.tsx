"use client";

import { useEffect, useState } from "react";
import { PickCard } from "@/components/discovery/PickCard";
import { FlowAlertPanel } from "@/components/discovery/FlowAlertPanel";
import { getFlowAlerts, getPicks, type DailyStockPick, type FlowAlert } from "@/lib/api";

export default function DiscoveryPage() {
  const [picks, setPicks] = useState<DailyStockPick[] | null>(null);
  const [flowAlerts, setFlowAlerts] = useState<FlowAlert[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getPicks("PENDING"), getFlowAlerts()])
      .then(([p, alerts]) => {
        setPicks(p);
        setFlowAlerts(alerts);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const flowByTicker = new Map(flowAlerts.map((a) => [a.ticker, a]));

  return (
    <div className="mx-auto max-w-5xl">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-cream">Daily Discovery</h1>
        <p className="mt-1 text-sm text-cream/60">
          Today&rsquo;s screened candidates, awaiting your manual approval. Nothing here is ever
          auto-invested.
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
          Could not reach the backend API ({error}). Is FastAPI running on NEXT_PUBLIC_API_BASE_URL?
        </div>
      )}

      <div className="mb-8">
        <FlowAlertPanel alerts={flowAlerts} />
      </div>

      <div className="space-y-4">
        {picks === null && !error && <p className="text-cream/50">Loading today&rsquo;s picks&hellip;</p>}
        {picks?.length === 0 && (
          <p className="text-cream/50">No pending picks right now &mdash; check back after the next screening run.</p>
        )}
        {picks?.map((pick) => (
          <PickCard
            key={pick.id}
            pick={pick}
            flowAlert={flowByTicker.get(pick.ticker)}
            onDecided={(updated) => setPicks((prev) => prev?.map((p) => (p.id === updated.id ? updated : p)) ?? null)}
          />
        ))}
      </div>
    </div>
  );
}
