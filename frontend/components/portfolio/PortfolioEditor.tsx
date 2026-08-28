"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { ComputedHolding, PortfolioHolding, PortfolioState } from "@/lib/portfolio";

interface PortfolioEditorProps {
  portfolio: PortfolioState;
  computedHoldings: ComputedHolding[];
  onChange: (next: PortfolioState) => void;
}

function fmtVnd(v: number): string {
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const inputClass = "mt-1 w-full rounded-md border border-brown-700 bg-brown-950 px-2.5 py-1.5 text-sm text-cream";

export function PortfolioEditor({ portfolio, computedHoldings, onChange }: PortfolioEditorProps) {
  const [draft, setDraft] = useState({ ticker: "", buyPrice: "", quantity: "" });

  function updateCash(raw: string) {
    onChange({ ...portfolio, cash: Number(raw.replace(/[^0-9.]/g, "")) || 0 });
  }

  function updateFee(raw: string) {
    onChange({ ...portfolio, feePct: Number(raw) || 0 });
  }

  function addHolding() {
    const ticker = draft.ticker.trim().toUpperCase();
    const buyPrice = Number(draft.buyPrice);
    const quantity = Number(draft.quantity);
    if (!ticker || !buyPrice || !quantity) return;
    const holding: PortfolioHolding = { id: makeId(), ticker, buyPrice, quantity };
    onChange({ ...portfolio, holdings: [...portfolio.holdings, holding] });
    setDraft({ ticker: "", buyPrice: "", quantity: "" });
  }

  function removeHolding(id: string) {
    onChange({ ...portfolio, holdings: portfolio.holdings.filter((h) => h.id !== id) });
  }

  const anyPriceMissing = computedHoldings.some((h) => !h.priceAvailable);

  return (
    <Card>
      <h2 className="mb-1 text-base font-semibold text-cream">Your Portfolio</h2>
      <p className="mb-4 text-xs text-cream/50">
        Stored only in this browser (localStorage) &mdash; there&rsquo;s no backend behind this site to
        save it to. Clearing browser data or switching devices loses it.
      </p>

      <div className="mb-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
        <label className="block">
          <span className="text-xs text-cream/50">Cash (VND)</span>
          <input
            type="text"
            inputMode="decimal"
            value={portfolio.cash === 0 ? "" : portfolio.cash.toLocaleString()}
            onChange={(e) => updateCash(e.target.value)}
            placeholder="0"
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="text-xs text-cream/50">Trading fee (% per side)</span>
          <input
            type="number"
            step="0.01"
            min="0"
            value={portfolio.feePct}
            onChange={(e) => updateFee(e.target.value)}
            className={inputClass}
          />
        </label>
      </div>

      {computedHoldings.length > 0 && (
        <div className="mb-4 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-brown-700/60 text-xs text-cream/50">
                <th className="py-2 pr-3 font-medium">Ticker</th>
                <th className="py-2 pr-3 font-medium">Qty</th>
                <th className="py-2 pr-3 font-medium">Buy Price</th>
                <th className="py-2 pr-3 font-medium">Last Price</th>
                <th className="py-2 pr-3 font-medium">Market Value</th>
                <th className="py-2 pr-3 font-medium">Unrealized P&amp;L (net of fees)</th>
                <th className="py-2 pr-3" />
              </tr>
            </thead>
            <tbody>
              {computedHoldings.map((h) => (
                <tr key={h.id} className="border-b border-brown-700/30">
                  <td className="py-2 pr-3 font-semibold text-cream">{h.ticker}</td>
                  <td className="py-2 pr-3 text-cream/80">{h.quantity.toLocaleString()}</td>
                  <td className="py-2 pr-3 text-cream/80">{fmtVnd(h.buyPrice)}</td>
                  <td className="py-2 pr-3 text-cream/80">
                    {h.priceAvailable ? fmtVnd(h.lastPrice as number) : <span className="text-cream/40">n/a</span>}
                  </td>
                  <td className="py-2 pr-3 text-cream/80">{fmtVnd(h.marketValue)}</td>
                  <td className={`py-2 pr-3 font-medium ${h.unrealizedPnlNet >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {h.unrealizedPnlNet >= 0 ? "+" : ""}
                    {fmtVnd(h.unrealizedPnlNet)}
                  </td>
                  <td className="py-2 pr-3 text-right">
                    <button onClick={() => removeHolding(h.id)} className="text-cream/40 hover:text-red-400" aria-label={`Remove ${h.ticker}`}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {anyPriceMissing && (
            <p className="mt-2 text-xs text-cream/40">
              &ldquo;n/a&rdquo; = this ticker isn&rsquo;t in the ~60-name universe this snapshot covers, so
              market value falls back to your buy price (no daily P&amp;L for it).
            </p>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <label className="block">
          <span className="text-xs text-cream/50">Ticker</span>
          <input
            value={draft.ticker}
            onChange={(e) => setDraft((d) => ({ ...d, ticker: e.target.value }))}
            placeholder="VNM"
            className="mt-1 w-24 rounded-md border border-brown-700 bg-brown-950 px-2.5 py-1.5 text-sm uppercase text-cream"
          />
        </label>
        <label className="block">
          <span className="text-xs text-cream/50">Buy price (VND)</span>
          <input
            type="number"
            value={draft.buyPrice}
            onChange={(e) => setDraft((d) => ({ ...d, buyPrice: e.target.value }))}
            placeholder="62500"
            className="mt-1 w-32 rounded-md border border-brown-700 bg-brown-950 px-2.5 py-1.5 text-sm text-cream"
          />
        </label>
        <label className="block">
          <span className="text-xs text-cream/50">Quantity</span>
          <input
            type="number"
            value={draft.quantity}
            onChange={(e) => setDraft((d) => ({ ...d, quantity: e.target.value }))}
            placeholder="100"
            className="mt-1 w-28 rounded-md border border-brown-700 bg-brown-950 px-2.5 py-1.5 text-sm text-cream"
          />
        </label>
        <Button onClick={addHolding} variant="ghost">
          <span className="flex items-center gap-1.5">
            <Plus className="h-4 w-4" /> Add holding
          </span>
        </Button>
      </div>
    </Card>
  );
}
