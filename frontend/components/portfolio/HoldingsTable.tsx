import { Badge } from "@/components/ui/Badge";
import { IS_READ_ONLY, type Holding } from "@/lib/api";

const STATUS_VARIANT = {
  OPEN: "success",
  SELL_SIGNAL: "danger",
  CLOSED: "neutral",
} as const;

export function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  if (holdings.length === 0) {
    return (
      <p className="text-sm text-cream/50">
        {IS_READ_ONLY
          ? "This is a read-only real-data snapshot with no brokerage integration — there are no real holdings to show."
          : "No holdings yet — approve a pick to open one."}
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-brown-700/60 text-cream/50">
            <th className="py-2 pr-4 font-medium">Ticker</th>
            <th className="py-2 pr-4 font-medium">Qty</th>
            <th className="py-2 pr-4 font-medium">Avg Cost</th>
            <th className="py-2 pr-4 font-medium">Peak</th>
            <th className="py-2 pr-4 font-medium">Stop</th>
            <th className="py-2 pr-4 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={h.id} className="border-b border-brown-700/30">
              <td className="py-2.5 pr-4 font-semibold text-cream">{h.ticker}</td>
              <td className="py-2.5 pr-4 text-cream/80">{h.quantity.toLocaleString()}</td>
              <td className="py-2.5 pr-4 text-cream/80">{h.avg_cost.toLocaleString()}</td>
              <td className="py-2.5 pr-4 text-cream/80">{h.peak_price_since_open.toLocaleString()}</td>
              <td className="py-2.5 pr-4 text-cream/80">{h.stop_loss_price?.toLocaleString() ?? "—"}</td>
              <td className="py-2.5 pr-4">
                <Badge variant={STATUS_VARIANT[h.status]}>{h.status}</Badge>
                {h.sell_signal_reason && (
                  <div className="mt-1 text-xs text-cream/50">{h.sell_signal_reason}</div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
