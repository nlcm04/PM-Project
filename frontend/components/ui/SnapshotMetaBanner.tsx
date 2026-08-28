"use client";

import { useEffect, useState } from "react";
import { getSnapshotMeta, type StaticSnapshotMeta } from "@/lib/api";

export function SnapshotMetaBanner() {
  const [meta, setMeta] = useState<StaticSnapshotMeta | null>(null);

  useEffect(() => {
    getSnapshotMeta()
      .then(setMeta)
      .catch(() => setMeta(null));
  }, []);

  if (!meta) return null;

  const generated = new Date(meta.generated_at);
  const generatedLabel = Number.isNaN(generated.getTime())
    ? meta.generated_at
    : generated.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

  return (
    <div className="mb-6 rounded-lg border border-brown-700/60 bg-brown-900/40 px-4 py-3 text-xs text-cream/60">
      <span className="font-medium text-cream/80">Real data, generated {generatedLabel}.</span>{" "}
      {meta.screened_count} of {meta.fetched_count} curated tickers passed the screen (universe of{" "}
      {meta.universe_size}, non-financial large caps only). Backtest evaluated out-of-sample over the
      last {meta.out_of_sample_days} trading days, held out from the {meta.in_sample_days} days used to
      derive the picks. {meta.note}
    </div>
  );
}
