"use client";

import { useEffect, useState } from "react";
import { getSnapshotMeta, type StaticSnapshotMeta } from "@/lib/api";

function minutesAgoLabel(generatedAt: string, nowMs: number): string {
  const generatedMs = new Date(generatedAt).getTime();
  if (Number.isNaN(generatedMs)) return "";
  const minutes = Math.max(0, Math.round((nowMs - generatedMs) / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m ago`;
}

export function SnapshotMetaBanner() {
  const [meta, setMeta] = useState<StaticSnapshotMeta | null>(null);
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    getSnapshotMeta()
      .then(setMeta)
      .catch(() => setMeta(null));
  }, []);

  useEffect(() => {
    setNow(Date.now());
    const interval = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(interval);
  }, []);

  if (!meta) return null;

  const generated = new Date(meta.generated_at);
  const generatedLabel = Number.isNaN(generated.getTime())
    ? meta.generated_at
    : generated.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

  return (
    <div className="mb-6 rounded-lg border border-brown-700/60 bg-brown-900/40 px-4 py-3 text-xs text-cream/60">
      <span className="font-medium text-cream/80">
        Real data, generated {generatedLabel}
        {now != null && ` (${minutesAgoLabel(meta.generated_at, now)})`}.
      </span>{" "}
      {meta.scoreable_count} of {meta.fetched_count} curated tickers scored ({meta.disqualified_count}{" "}
      disqualified) out of a universe of {meta.universe_size}, sector-neutral across {meta.factors.length}{" "}
      factors (value, quality, 12-1 month momentum, foreign flow).{" "}
      {meta.walk_forward_folds != null && (
        <>Shortlist backtest is walk-forward across {meta.walk_forward_folds} historical folds. </>
      )}
      Foreign-flow history: {meta.foreign_flow_history_days} day{meta.foreign_flow_history_days === 1 ? "" : "s"}{" "}
      accumulated so far. Refreshes hourly during HOSE trading hours. {meta.note}
    </div>
  );
}
