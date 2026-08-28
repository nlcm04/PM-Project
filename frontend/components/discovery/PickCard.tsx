"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FlowAlertBadge } from "@/components/discovery/FlowAlertBadge";
import { approvePick, IS_READ_ONLY, rejectPick, type DailyStockPick, type FlowAlert } from "@/lib/api";
import { ordinal } from "@/lib/format";

interface PickCardProps {
  pick: DailyStockPick;
  flowAlert?: FlowAlert;
  onDecided: (updated: DailyStockPick) => void;
}

export function PickCard({ pick, flowAlert, onDecided }: PickCardProps) {
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);

  async function handle(action: "approve" | "reject") {
    setBusy(action);
    try {
      const updated = await (action === "approve" ? approvePick(pick.id) : rejectPick(pick.id));
      onDecided(updated);
    } finally {
      setBusy(null);
    }
  }

  const backtest = pick.backtest_summary ?? {};

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-cream">{pick.ticker}</h3>
            <span className="text-sm text-cream/50">{pick.company_name}</span>
          </div>
          <p className="mt-1 text-sm text-cream/70">{pick.rationale}</p>
        </div>
        <Badge variant="amber">weight {(pick.suggested_weight * 100).toFixed(1)}%</Badge>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Badge>Projected Sharpe {pick.projected_sharpe.toFixed(2)}</Badge>
        {typeof backtest.vs_random_baskets_percentile === "number" && (
          <Badge>{ordinal(backtest.vs_random_baskets_percentile as number)} pct vs. random baskets</Badge>
        )}
        {flowAlert && <FlowAlertBadge alert={flowAlert} />}
      </div>

      {pick.status === "PENDING" ? (
        IS_READ_ONLY ? (
          <p className="mt-5 text-xs text-cream/40">
            Read-only real-data snapshot &mdash; approvals can&rsquo;t be persisted without a live backend.
          </p>
        ) : (
          <div className="mt-5 flex gap-2">
            <Button onClick={() => handle("approve")} disabled={busy !== null}>
              <span className="flex items-center gap-1.5">
                <Check className="h-4 w-4" /> Approve
              </span>
            </Button>
            <Button variant="ghost" onClick={() => handle("reject")} disabled={busy !== null}>
              <span className="flex items-center gap-1.5">
                <X className="h-4 w-4" /> Reject
              </span>
            </Button>
          </div>
        )
      ) : (
        <div className="mt-5">
          <Badge variant={pick.status === "APPROVED" ? "success" : "danger"}>{pick.status}</Badge>
        </div>
      )}
    </Card>
  );
}
