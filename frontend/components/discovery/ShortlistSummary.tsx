import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { DailyStockPick } from "@/lib/api";
import { ordinal } from "@/lib/format";

export function ShortlistSummary({ picks }: { picks: DailyStockPick[] }) {
  if (picks.length === 0) return null;

  return (
    <Card className="mb-8">
      <h2 className="mb-1 text-base font-semibold text-cream">Today&rsquo;s Optimizer Shortlist</h2>
      <p className="mb-4 text-xs text-cream/50">
        The max-Sharpe optimizer&rsquo;s picks from the ranked table below (marked ★), sized with weights
        derived from all available history. The Sharpe shown is walk-forward across multiple historical
        folds (expanding-window re-optimization each time), not a single static backtest.
      </p>
      <div className="space-y-3">
        {picks.map((pick) => {
          const nFolds = pick.backtest_summary?.walk_forward_n_folds as number | undefined;
          const vsRandom = pick.backtest_summary?.vs_random_baskets_percentile as number | null | undefined;
          return (
            <div key={pick.id} className="flex items-start justify-between gap-4 border-t border-brown-700/40 pt-3 first:border-t-0 first:pt-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-cream">{pick.ticker}</span>
                  <Badge variant="amber">weight {(pick.suggested_weight * 100).toFixed(1)}%</Badge>
                </div>
                <p className="mt-1 text-xs text-cream/60">{pick.rationale}</p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <Badge>
                  {nFolds ? `${nFolds}-fold walk-forward Sharpe` : "Basket Sharpe"} {pick.projected_sharpe.toFixed(2)}
                </Badge>
                {typeof vsRandom === "number" && <Badge variant="neutral">{ordinal(vsRandom)} pct vs. random baskets</Badge>}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
