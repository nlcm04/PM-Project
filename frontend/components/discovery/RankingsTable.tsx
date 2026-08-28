"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, TrendingDown, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { RankedStock } from "@/lib/api";

type SortKey =
  | "ticker"
  | "sector"
  | "composite_score"
  | "percentile_rank"
  | "earnings_yield"
  | "book_to_market"
  | "ev_to_ebitda"
  | "roic"
  | "cfo_to_assets"
  | "interest_coverage"
  | "momentum"
  | "foreign_flow_5d"
  | "last_price"
  | "price_change_pct"
  | "relative_volume"
  | "volume_zscore";

const fmtPctFraction = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
const fmtPctAlready = (v: number | null) => (v == null ? "—" : `${v.toFixed(1)}%`);
const fmtRatio = (v: number | null) => (v == null ? "—" : `${v.toFixed(2)}x`);
const fmtVnd = (v: number | null) => (v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 0 }));

/** Foreign-flow values are net VND traded by foreign investors, often in the
 * billions -- a compact "+12.5B" reads far better in a table cell than the
 * full number.
 */
const fmtCompactVnd = (v: number | null) => {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "-";
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(0)}M`;
  return `${sign}${abs.toFixed(0)}`;
};

interface Column {
  key: SortKey;
  label: string;
  format: (r: RankedStock) => string;
  align?: "left" | "right";
}

const COLUMNS: Column[] = [
  { key: "ticker", label: "Ticker", format: (r) => r.ticker },
  { key: "sector", label: "Sector", format: (r) => r.sector },
  { key: "composite_score", label: "Score", format: (r) => (r.composite_score != null ? r.composite_score.toFixed(2) : "—"), align: "right" },
  { key: "percentile_rank", label: "Pct", format: (r) => (r.percentile_rank != null ? `${r.percentile_rank.toFixed(0)}%` : "—"), align: "right" },
  { key: "earnings_yield", label: "E/P", format: (r) => fmtPctFraction(r.earnings_yield), align: "right" },
  { key: "book_to_market", label: "B/M", format: (r) => (r.book_to_market != null ? r.book_to_market.toFixed(2) : "—"), align: "right" },
  { key: "ev_to_ebitda", label: "EV/EBITDA", format: (r) => fmtRatio(r.ev_to_ebitda), align: "right" },
  { key: "roic", label: "ROIC", format: (r) => fmtPctAlready(r.roic), align: "right" },
  { key: "cfo_to_assets", label: "CFO/Assets", format: (r) => fmtPctFraction(r.cfo_to_assets), align: "right" },
  { key: "interest_coverage", label: "Int. Cov.", format: (r) => fmtRatio(r.interest_coverage), align: "right" },
  { key: "momentum", label: "Mom. 12-1", format: (r) => fmtPctFraction(r.momentum), align: "right" },
  { key: "foreign_flow_5d", label: "Foreign 5d", format: (r) => fmtCompactVnd(r.foreign_flow_5d), align: "right" },
  { key: "last_price", label: "Price (₫)", format: (r) => fmtVnd(r.last_price), align: "right" },
  { key: "price_change_pct", label: "Chg", format: (r) => fmtPctFraction(r.price_change_pct), align: "right" },
  { key: "relative_volume", label: "Rel.Vol", format: (r) => (r.relative_volume != null ? `${r.relative_volume.toFixed(1)}x` : "—"), align: "right" },
  { key: "volume_zscore", label: "Vol Z", format: (r) => (r.volume_zscore != null ? r.volume_zscore.toFixed(1) : "—"), align: "right" },
];

/** Compares two rows on `key`, with `direction` applied ONLY to non-null
 * comparisons -- nulls always sort last regardless of asc/desc. Applying the
 * direction multiplier uniformly (including to the null case) would flip
 * "nulls last" into "nulls first" whenever sorting descending, which is
 * exactly backwards for a "best to worst" ranking table.
 */
function compareValues(a: RankedStock, b: RankedStock, key: SortKey, direction: "asc" | "desc"): number {
  const av = a[key];
  const bv = b[key];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  const cmp = typeof av === "string" && typeof bv === "string" ? av.localeCompare(bv) : av < bv ? -1 : av > bv ? 1 : 0;
  return direction === "asc" ? cmp : -cmp;
}

export function RankingsTable({ rows, pickTickers }: { rows: RankedStock[]; pickTickers: Set<string> }) {
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => compareValues(a, b, sortKey, sortDir));
    return copy;
  }, [rows, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  if (rows.length === 0) {
    return <p className="text-sm text-cream/50">No ranking data available yet.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-brown-700/60">
      <table className="w-full min-w-[1000px] text-left text-sm">
        <thead className="bg-brown-900/60">
          <tr>
            <th className="w-8" />
            {COLUMNS.map((col) => {
              const active = col.key === sortKey;
              return (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  className={`cursor-pointer select-none whitespace-nowrap px-3 py-2.5 text-xs font-semibold text-cream/60 hover:text-cream ${
                    col.align === "right" ? "text-right" : "text-left"
                  }`}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {active ? (
                      sortDir === "asc" ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      )
                    ) : (
                      <ArrowUpDown className="h-3 w-3 opacity-30" />
                    )}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={row.ticker}
              title={row.disqualified ? row.disqualification_reasons.join("; ") : undefined}
              className={`border-t border-brown-700/40 ${row.disqualified ? "opacity-40" : ""} hover:bg-brown-900/30`}
            >
              <td className="px-2">
                {pickTickers.has(row.ticker) && <Badge variant="amber">★</Badge>}
              </td>
              {COLUMNS.map((col) => (
                <td
                  key={col.key}
                  className={`whitespace-nowrap px-3 py-2 text-cream/80 ${col.align === "right" ? "text-right tabular-nums" : ""} ${
                    col.key === "ticker" ? "font-semibold text-cream" : ""
                  }`}
                >
                  {col.key === "price_change_pct" && row.price_change_pct != null ? (
                    <span className={`inline-flex items-center gap-1 ${row.price_change_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {row.price_change_pct >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                      {col.format(row)}
                    </span>
                  ) : col.key === "foreign_flow_5d" && row.foreign_flow_5d != null ? (
                    <span className={row.foreign_flow_5d >= 0 ? "text-emerald-400" : "text-red-400"}>{col.format(row)}</span>
                  ) : (
                    col.format(row)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-brown-700/40 bg-brown-900/30 px-3 py-2 text-xs text-cream/40">
        ★ = in today&rsquo;s optimizer-selected shortlist. Faded rows are disqualified (hover for reason in
        the row) or missing enough data to score.
      </p>
    </div>
  );
}
