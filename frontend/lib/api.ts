const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Set at build time for the GitHub Pages demo (see .github/workflows/deploy_frontend.yml).
// In demo mode every function below returns static fixture data instead of
// calling a backend -- there is no FastAPI/Postgres behind the Pages deploy.
const IS_DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

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

// Lazily imported so the sample fixtures never end up in a non-demo production
// bundle's initial chunk analysis just for being referenced at module scope.
async function loadDemoData() {
  return import("./sampleData");
}

let demoPicksCache: DailyStockPick[] | null = null;

export const getPicks = async (status?: PickStatus): Promise<DailyStockPick[]> => {
  if (IS_DEMO) {
    if (!demoPicksCache) {
      const { SAMPLE_PICKS } = await loadDemoData();
      demoPicksCache = SAMPLE_PICKS.map((p) => ({ ...p }));
    }
    return status ? demoPicksCache.filter((p) => p.status === status) : demoPicksCache;
  }
  return apiFetch<DailyStockPick[]>(`/api/picks${status ? `?status=${status}` : ""}`);
};

async function decideDemoPick(id: number, status: PickStatus, decidedBy: string): Promise<DailyStockPick> {
  if (!demoPicksCache) await getPicks();
  const pick = demoPicksCache!.find((p) => p.id === id);
  if (!pick) throw new Error(`Demo pick ${id} not found`);
  pick.status = status;
  pick.decided_at = new Date().toISOString();
  pick.decided_by = decidedBy;
  return { ...pick };
}

export const approvePick = (id: number, decidedBy = "user") =>
  IS_DEMO
    ? decideDemoPick(id, "APPROVED", decidedBy)
    : apiFetch<DailyStockPick>(`/api/picks/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ decided_by: decidedBy }),
      });

export const rejectPick = (id: number, decidedBy = "user") =>
  IS_DEMO
    ? decideDemoPick(id, "REJECTED", decidedBy)
    : apiFetch<DailyStockPick>(`/api/picks/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ decided_by: decidedBy }),
      });

export const getHoldings = async (): Promise<Holding[]> => {
  if (IS_DEMO) {
    const { SAMPLE_HOLDINGS } = await loadDemoData();
    return SAMPLE_HOLDINGS;
  }
  return apiFetch<Holding[]>("/api/holdings");
};

export const getPerformanceHealth = async (limit = 180): Promise<PerformanceSnapshot[]> => {
  if (IS_DEMO) {
    const { SAMPLE_PERFORMANCE } = await loadDemoData();
    return SAMPLE_PERFORMANCE.slice(-limit);
  }
  return apiFetch<PerformanceSnapshot[]>(`/api/performance/health?limit=${limit}`);
};

export const getFlowAlerts = async (days = 7, onlyAnomalous = true): Promise<FlowAlert[]> => {
  if (IS_DEMO) {
    const { SAMPLE_FLOW_ALERTS } = await loadDemoData();
    return onlyAnomalous ? SAMPLE_FLOW_ALERTS.filter((a) => a.is_anomalous) : SAMPLE_FLOW_ALERTS;
  }
  return apiFetch<FlowAlert[]>(`/api/flow-alerts?days=${days}&only_anomalous=${onlyAnomalous}`);
};
