// Static sample data for the GitHub Pages demo build (NEXT_PUBLIC_DEMO_MODE=true).
// This is fixture data for showing the UI -- it does not come from a real
// screening run, a real backtest, or a real brokerage. See README.md.

import type { DailyStockPick, FlowAlert, Holding, PerformanceSnapshot } from "./api";

export const SAMPLE_PICKS: DailyStockPick[] = [
  {
    id: 1,
    asset_id: 101,
    ticker: "FPT",
    company_name: "FPT Corporation",
    pick_date: "2026-08-27",
    rationale:
      "Composite score at 92nd percentile; Grinold expected active return 0.0184. High ROIC, positive CFO/Assets, interest coverage 14.2x.",
    projected_sharpe: 1.42,
    suggested_weight: 0.18,
    backtest_summary: { vs_random_baskets_percentile: 97, sharpe_ratio: 1.42, n_periods: 126 },
    status: "PENDING",
    decided_at: null,
    decided_by: null,
  },
  {
    id: 2,
    asset_id: 102,
    ticker: "ACB",
    company_name: "Asia Commercial Bank",
    pick_date: "2026-08-27",
    rationale:
      "Composite score at 84th percentile; Grinold expected active return 0.0121. Cheap on B/M, clean governance, no filing issues.",
    projected_sharpe: 1.15,
    suggested_weight: 0.14,
    backtest_summary: { vs_random_baskets_percentile: 89, sharpe_ratio: 1.15, n_periods: 126 },
    status: "PENDING",
    decided_at: null,
    decided_by: null,
  },
  {
    id: 3,
    asset_id: 103,
    ticker: "HPG",
    company_name: "Hoa Phat Group",
    pick_date: "2026-08-27",
    rationale:
      "Composite score at 78th percentile; Grinold expected active return 0.0097. Low EV/EBITDA vs sector, ROIC recovering.",
    projected_sharpe: 0.98,
    suggested_weight: 0.11,
    backtest_summary: { vs_random_baskets_percentile: 81, sharpe_ratio: 0.98, n_periods: 126 },
    status: "PENDING",
    decided_at: null,
    decided_by: null,
  },
  {
    id: 4,
    asset_id: 104,
    ticker: "VNM",
    company_name: "Vietnam Dairy Products",
    pick_date: "2026-08-26",
    rationale:
      "Composite score at 88th percentile; Grinold expected active return 0.0143. Approved for stable cash flow and dividend coverage.",
    projected_sharpe: 1.28,
    suggested_weight: 0.16,
    backtest_summary: { vs_random_baskets_percentile: 93, sharpe_ratio: 1.28, n_periods: 126 },
    status: "APPROVED",
    decided_at: "2026-08-26T08:41:00Z",
    decided_by: "user",
  },
];

export const SAMPLE_FLOW_ALERTS: FlowAlert[] = [
  {
    id: 1,
    asset_id: 101,
    ticker: "FPT",
    as_of_date: "2026-08-27",
    relative_volume: 4.3,
    volume_zscore: 3.1,
    price_change_pct: 0.028,
    direction: "ACCUMULATION",
    foreign_net_value: 42_500_000_000,
    is_anomalous: true,
    created_at: "2026-08-27T08:05:00Z",
  },
  {
    id: 2,
    asset_id: 105,
    ticker: "VIC",
    as_of_date: "2026-08-27",
    relative_volume: 3.6,
    volume_zscore: 2.8,
    price_change_pct: -0.019,
    direction: "DISTRIBUTION",
    foreign_net_value: -18_200_000_000,
    is_anomalous: true,
    created_at: "2026-08-27T08:05:00Z",
  },
];

export const SAMPLE_HOLDINGS: Holding[] = [
  {
    id: 1,
    asset_id: 104,
    ticker: "VNM",
    quantity: 2000,
    avg_cost: 61_500,
    opened_at: "2026-06-02",
    closed_at: null,
    peak_price_since_open: 64_800,
    stop_loss_price: 58_800,
    status: "OPEN",
    sell_signal_reason: null,
  },
  {
    id: 2,
    asset_id: 106,
    ticker: "MWG",
    quantity: 1500,
    avg_cost: 48_200,
    opened_at: "2026-04-14",
    closed_at: null,
    peak_price_since_open: 55_100,
    stop_loss_price: 47_350,
    status: "SELL_SIGNAL",
    sell_signal_reason: "Composite score below 30th percentile for 2 consecutive quarters",
  },
  {
    id: 3,
    asset_id: 107,
    ticker: "REE",
    quantity: 1200,
    avg_cost: 71_000,
    opened_at: "2026-02-10",
    closed_at: "2026-07-20",
    peak_price_since_open: 82_400,
    stop_loss_price: 74_300,
    status: "CLOSED",
    sell_signal_reason: "Trailing stop breached: price < 2.5x-ATR stop",
  },
];

function buildSamplePerformanceHistory(): PerformanceSnapshot[] {
  const snapshots: PerformanceSnapshot[] = [];
  let nav = 1_000_000_000;
  const start = new Date("2026-02-01T00:00:00Z");

  for (let i = 0; i < 130; i++) {
    const date = new Date(start);
    date.setDate(date.getDate() + i);
    // Deterministic pseudo-random walk so the demo is stable across builds.
    const wobble = Math.sin(i / 9) * 0.006 + Math.sin(i / 37) * 0.003;
    nav = nav * (1 + 0.0009 + wobble);

    snapshots.push({
      id: i + 1,
      snapshot_date: date.toISOString().slice(0, 10),
      nav: Math.round(nav),
      sharpe_ratio: 1.05 + Math.sin(i / 20) * 0.25,
      max_drawdown: -Math.abs(0.04 + Math.sin(i / 15) * 0.03),
      factor_exposures: {
        "E/P": 0.6 + Math.sin(i / 25) * 0.1,
        "B/M": 0.4 + Math.cos(i / 22) * 0.1,
        ROIC: 0.7 + Math.sin(i / 18) * 0.08,
        "CFO/Assets": 0.35 + Math.cos(i / 30) * 0.05,
      },
      diagnostics: {
        adf_forward_returns: { is_stationary: true, p_value: 0.012 },
        breusch_pagan: { heteroskedastic: false, lm_p_value: 0.31 },
        breusch_godfrey: { serially_correlated: false, lm_p_value: 0.44 },
      },
    });
  }
  return snapshots;
}

export const SAMPLE_PERFORMANCE: PerformanceSnapshot[] = buildSamplePerformanceHistory();
