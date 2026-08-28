"use client";

import { TrendingDown, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { FlowAlert } from "@/lib/api";

export function FlowAlertPanel({ alerts }: { alerts: FlowAlert[] }) {
  if (alerts.length === 0) {
    return (
      <Card>
        <h2 className="text-base font-semibold text-cream">Unusual Buying Activity</h2>
        <p className="mt-2 text-sm text-cream/50">
          No volume anomalies detected in the last few sessions across the tracked universe.
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="text-base font-semibold text-cream">Unusual Buying Activity</h2>
      <p className="mt-1 text-xs text-cream/50">
        Stocks trading at a statistically unusual multiple of their own historical volume today
        &mdash; a proxy for institutional accumulation/distribution, not a buy/sell recommendation.
      </p>
      <ul className="mt-4 divide-y divide-brown-700/60">
        {alerts.map((alert) => {
          const isBuying = alert.direction === "ACCUMULATION";
          return (
            <li key={alert.id} className="flex items-center justify-between py-3">
              <div className="flex items-center gap-3">
                {isBuying ? (
                  <TrendingUp className="h-4 w-4 text-emerald-400" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-red-400" />
                )}
                <div>
                  <div className="font-semibold text-cream">{alert.ticker}</div>
                  <div className="text-xs text-cream/50">
                    {alert.relative_volume.toFixed(1)}x avg volume · z-score {alert.volume_zscore.toFixed(1)} ·{" "}
                    {(alert.price_change_pct * 100).toFixed(1)}% on the day
                  </div>
                </div>
              </div>
              <Badge variant={isBuying ? "success" : "danger"}>{alert.direction}</Badge>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
