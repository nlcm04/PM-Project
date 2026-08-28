// Personal portfolio tracking, stored entirely in the viewer's own browser
// (localStorage) -- there is no backend behind the deployed site to persist
// this to, and it is private to whichever browser/device it was entered on.
// See README.md for that trade-off.

export interface PortfolioHolding {
  id: string;
  ticker: string;
  buyPrice: number; // whole VND per share
  quantity: number;
}

export interface PortfolioState {
  cash: number; // whole VND
  feePct: number; // e.g. 0.1 meaning 0.1% per trade side
  holdings: PortfolioHolding[];
}

export interface NavHistoryPoint {
  date: string; // YYYY-MM-DD
  nav: number;
}

export const DEFAULT_PORTFOLIO: PortfolioState = {
  cash: 0,
  feePct: 0.1,
  holdings: [],
};

const PORTFOLIO_KEY = "hose-quant:portfolio:v1";
const NAV_HISTORY_KEY = "hose-quant:nav-history:v1";

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // private browsing, storage disabled, etc.
  }
}

function safeSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // ignore -- best-effort persistence only
  }
}

export function loadPortfolio(): PortfolioState {
  const raw = safeGet(PORTFOLIO_KEY);
  if (!raw) return DEFAULT_PORTFOLIO;
  try {
    const parsed = JSON.parse(raw);
    return {
      cash: typeof parsed.cash === "number" ? parsed.cash : DEFAULT_PORTFOLIO.cash,
      feePct: typeof parsed.feePct === "number" ? parsed.feePct : DEFAULT_PORTFOLIO.feePct,
      holdings: Array.isArray(parsed.holdings) ? parsed.holdings : [],
    };
  } catch {
    return DEFAULT_PORTFOLIO;
  }
}

export function savePortfolio(state: PortfolioState): void {
  safeSet(PORTFOLIO_KEY, JSON.stringify(state));
}

export function loadNavHistory(): NavHistoryPoint[] {
  const raw = safeGet(NAV_HISTORY_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/** Upserts today's NAV into the client-side history (one point per calendar day). */
export function recordNavHistoryPoint(nav: number): NavHistoryPoint[] {
  const history = loadNavHistory();
  const today = new Date().toISOString().slice(0, 10);
  const idx = history.findIndex((p) => p.date === today);
  if (idx >= 0) history[idx] = { date: today, nav };
  else history.push({ date: today, nav });
  history.sort((a, b) => a.date.localeCompare(b.date));
  safeSet(NAV_HISTORY_KEY, JSON.stringify(history));
  return history;
}

export interface ComputedHolding extends PortfolioHolding {
  lastPrice: number | null;
  priceAvailable: boolean;
  marketValue: number;
  costBasis: number;
  unrealizedPnlGross: number;
  unrealizedPnlNet: number;
}

/** `priceByTicker` should hold whole-VND prices, keyed by uppercase ticker. */
export function computeHoldings(state: PortfolioState, priceByTicker: Map<string, number>): ComputedHolding[] {
  const feeRate = state.feePct / 100;
  return state.holdings.map((h) => {
    const lastPrice = priceByTicker.get(h.ticker.toUpperCase()) ?? null;
    const priceAvailable = lastPrice != null;
    const effectivePrice = lastPrice ?? h.buyPrice;
    const marketValue = effectivePrice * h.quantity;
    const costBasis = h.buyPrice * h.quantity * (1 + feeRate);
    const grossPnl = (effectivePrice - h.buyPrice) * h.quantity;
    const entryFee = h.buyPrice * h.quantity * feeRate;
    const exitFee = effectivePrice * h.quantity * feeRate;
    return {
      ...h,
      lastPrice,
      priceAvailable,
      marketValue,
      costBasis,
      unrealizedPnlGross: grossPnl,
      unrealizedPnlNet: grossPnl - entryFee - exitFee,
    };
  });
}

export function computeNav(state: PortfolioState, computed: ComputedHolding[]): number {
  return state.cash + computed.reduce((sum, h) => sum + h.marketValue, 0);
}

const TRADING_DAYS_PER_YEAR = 252;
const MIN_POINTS_FOR_SHARPE = 5;

/** Annualized Sharpe from the viewer's own recorded NAV history (one point per
 * calendar day they visited, not one per trading day) -- a rough personal
 * estimate, not a rigorous trading-day-aligned calculation. Null until
 * there's enough history to mean anything.
 */
export function computeHistorySharpe(history: NavHistoryPoint[]): number | null {
  if (history.length < MIN_POINTS_FOR_SHARPE) return null;
  const returns: number[] = [];
  for (let i = 1; i < history.length; i++) {
    const prev = history[i - 1].nav;
    if (prev > 0) returns.push((history[i].nav - prev) / prev);
  }
  if (returns.length < MIN_POINTS_FOR_SHARPE - 1) return null;
  const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
  const variance = returns.reduce((a, b) => a + (b - mean) ** 2, 0) / returns.length;
  const std = Math.sqrt(variance);
  return std === 0 ? null : Math.sqrt(TRADING_DAYS_PER_YEAR) * (mean / std);
}

export function computeHistoryMaxDrawdown(history: NavHistoryPoint[]): number | null {
  if (history.length < 2) return null;
  let peak = -Infinity;
  let maxDrawdown = 0;
  for (const point of history) {
    if (point.nav > peak) peak = point.nav;
    const drawdown = peak > 0 ? (point.nav - peak) / peak : 0;
    if (drawdown < maxDrawdown) maxDrawdown = drawdown;
  }
  return maxDrawdown;
}
