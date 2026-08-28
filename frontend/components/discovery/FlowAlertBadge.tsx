import { TrendingUp, TrendingDown } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { FlowAlert } from "@/lib/api";

export function FlowAlertBadge({ alert }: { alert: FlowAlert }) {
  if (alert.direction === "NEUTRAL") return null;

  const isBuying = alert.direction === "ACCUMULATION";
  return (
    <Badge variant={isBuying ? "success" : "danger"}>
      <span className="flex items-center gap-1">
        {isBuying ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
        {alert.relative_volume.toFixed(1)}x avg volume · {isBuying ? "accumulation" : "distribution"}
      </span>
    </Badge>
  );
}
