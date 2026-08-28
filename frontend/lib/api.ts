const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type PickStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface DailyStockPick {
  id: number;
  asset_id: number;
  ticker: string;
  company_name: string;
  pick_date: string;
  rationale: string;
  projected_sharpe: number;
  suggested_weight: number;
  backtest_summary: Record<string, unknown>;
  status: PickStatus;
  decided_at: string | null;
  decided_by: string | null;
}

export interface Holding {
  id: number;
  asset_id: number;
  ticker: string;
  quantity: number;
  avg_cost: number;
  opened_at: string;
  closed_at: string | null;
  peak_price_since_open: number;
  stop_loss_price: number | null;
  status: "OPEN" | "SELL_SIGNAL" | "CLOSED";
  sell_signal_reason: string | null;
}

export interface PerformanceSnapshot {
  id: number;
  snapshot_date: string;
  nav: number;
  sharpe_ratio: number;
  max_drawdown: number;
  factor_exposures: Record<string, number>;
  diagnostics: Record<string, unknown>;
}

export interface FlowAlert {
  id: number;
  asset_id: number;
  ticker: string;
  as_of_date: string;
  relative_volume: number;
  volume_zscore: number;
  price_change_pct: number;
  direction: "ACCUMULATION" | "DISTRIBUTION" | "NEUTRAL";
  foreign_net_value: number | null;
  is_anomalous: boolean;
  created_at: string;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status} ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export const getPicks = (status?: PickStatus) =>
  apiFetch<DailyStockPick[]>(`/api/picks${status ? `?status=${status}` : ""}`);

export const approvePick = (id: number, decidedBy = "user") =>
  apiFetch<DailyStockPick>(`/api/picks/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ decided_by: decidedBy }),
  });

export const rejectPick = (id: number, decidedBy = "user") =>
  apiFetch<DailyStockPick>(`/api/picks/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ decided_by: decidedBy }),
  });

export const getHoldings = () => apiFetch<Holding[]>("/api/holdings");

export const getPerformanceHealth = (limit = 180) =>
  apiFetch<PerformanceSnapshot[]>(`/api/performance/health?limit=${limit}`);

export const getFlowAlerts = (days = 7, onlyAnomalous = true) =>
  apiFetch<FlowAlert[]>(`/api/flow-alerts?days=${days}&only_anomalous=${onlyAnomalous}`);
