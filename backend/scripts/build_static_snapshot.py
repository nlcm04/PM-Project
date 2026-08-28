"""Generate a static, real-data JSON snapshot for the GitHub Pages demo.

GitHub Pages only serves static files, so this runs the real screening +
backtest pipeline in-memory against live vnstock data -- no database
required -- and writes plain JSON that the static frontend fetches directly.
Everything numeric here comes from a real vnstock pull; nothing is fabricated.

Factor set (7, cross-sectionally combined into `composite_score`):
  earnings_yield, book_to_market, ev_to_ebitda, roic, cfo_to_assets  (value/quality, from fundamentals)
  momentum_12_1                                                      (price-based, from OHLCV)
  foreign_flow_5d                                                    (rolling foreign net-buy, persisted across runs)
Scoring is SECTOR-NEUTRAL (app.quant.factors.sector_neutral_composite_score):
a bank's ratios are z-scored against other financials, not against real
estate or industrials -- pooling them cross-sector would bias the ranking
toward whichever sector happens to be cheap right now, not the cheapest name
within its own sector.

Deliberate scope limits, stated here rather than hidden:

1. ~60 hand-picked liquid HOSE large/mid caps across sectors (see UNIVERSE
   below), not the full ~723-ticker HOSE listing. vnstock's free-tier rate
   limiter was observed live to kill the whole Python process with
   SystemExit (not a catchable Exception) after roughly 10 tickers' worth of
   calls when made too fast -- pulling the full universe every run, at a
   pace that avoids that, would take well over an hour and defeat the point
   of an hourly refresh.
2. Governance fields (auditor opinion, filing status, HOSE warning list) are
   NOT available from vnstock (see app/data/vnstock_client.py). Every
   ticker here is assumed governance-clean because it's a hand-picked
   large/mid-cap list, not because it was actually checked against HOSE
   disclosures.
3. Foreign flow is a LIVE SNAPSHOT persisted across runs into
   data/foreign_flow_history.json (committed back to the repo by CI -- see
   .github/workflows/deploy_frontend.yml), not a real historical time
   series -- vnstock has no verified historical foreign-flow endpoint
   (checked live: `Trading.history()` isn't actually implemented for either
   source despite appearing in the class's method list). The `foreign_flow_5d`
   factor is a rolling sum over however many days have accumulated since
   this feature shipped; it starts thin and improves day by day.
4. Walk-forward backtest validates the WEIGHT-DERIVATION methodology across
   multiple historical folds (expanding-window re-optimization, evaluated
   out-of-sample per fold, folds concatenated into one multi-regime curve --
   see app/quant/backtest.py::walk_forward_evaluate), not a single 70/30
   split. It does NOT re-select stocks at each historical fold using
   point-in-time historical fundamentals (vnstock's Finance.ratio() does
   return multiple historical quarters, so this is possible in principle,
   just not implemented here) -- today's stock selection is held fixed and
   only the portfolio-construction step is walked forward.
5. "Portfolio Health" (in the default, no-user-portfolio state) shows the
   walk-forward equity curve of the top-N shortlist, not a real brokerage
   account. holdings.json is intentionally empty -- real holdings live in
   the viewer's own browser (localStorage), entered by hand on the site.

Usage: python -m scripts.build_static_snapshot --out ../frontend/public/data
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app.data import vnstock_client
from app.quant import backtest, diagnostics, factors, governance, grinold, optimizer, order_flow
from app.quant.governance import GovernanceCheckInput
from app.utils import ordinal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_static_snapshot")

# Hand-picked liquid HOSE large/mid caps, spanning sectors incl. financials
# (see module docstring for how those are scored).
UNIVERSE = [
    {"ticker": "VNM", "sector": "Consumer"},
    {"ticker": "MWG", "sector": "Consumer"},
    {"ticker": "MSN", "sector": "Consumer"},
    {"ticker": "SAB", "sector": "Consumer"},
    {"ticker": "PNJ", "sector": "Consumer"},
    {"ticker": "FRT", "sector": "Consumer"},
    {"ticker": "DBC", "sector": "Consumer"},
    {"ticker": "VIC", "sector": "Real Estate"},
    {"ticker": "VHM", "sector": "Real Estate"},
    {"ticker": "VRE", "sector": "Real Estate"},
    {"ticker": "NVL", "sector": "Real Estate"},
    {"ticker": "KDH", "sector": "Real Estate"},
    {"ticker": "DXG", "sector": "Real Estate"},
    {"ticker": "PDR", "sector": "Real Estate"},
    {"ticker": "NLG", "sector": "Real Estate"},
    {"ticker": "DIG", "sector": "Real Estate"},
    {"ticker": "CII", "sector": "Real Estate"},
    {"ticker": "VCG", "sector": "Construction"},
    {"ticker": "HDG", "sector": "Real Estate"},
    {"ticker": "VCB", "sector": "Financials"},
    {"ticker": "BID", "sector": "Financials"},
    {"ticker": "CTG", "sector": "Financials"},
    {"ticker": "TCB", "sector": "Financials"},
    {"ticker": "MBB", "sector": "Financials"},
    {"ticker": "ACB", "sector": "Financials"},
    {"ticker": "VPB", "sector": "Financials"},
    {"ticker": "STB", "sector": "Financials"},
    {"ticker": "HDB", "sector": "Financials"},
    {"ticker": "SHB", "sector": "Financials"},
    {"ticker": "EIB", "sector": "Financials"},
    {"ticker": "LPB", "sector": "Financials"},
    {"ticker": "TPB", "sector": "Financials"},
    {"ticker": "SSI", "sector": "Financials"},
    {"ticker": "VND", "sector": "Financials"},
    {"ticker": "VCI", "sector": "Financials"},
    {"ticker": "HCM", "sector": "Financials"},
    {"ticker": "VIX", "sector": "Financials"},
    {"ticker": "BVH", "sector": "Financials"},
    {"ticker": "HPG", "sector": "Industrials"},
    {"ticker": "HSG", "sector": "Industrials"},
    {"ticker": "NKG", "sector": "Industrials"},
    {"ticker": "DGC", "sector": "Industrials"},
    {"ticker": "DPM", "sector": "Industrials"},
    {"ticker": "DCM", "sector": "Industrials"},
    {"ticker": "GVR", "sector": "Industrials"},
    {"ticker": "VGC", "sector": "Industrials"},
    {"ticker": "KBC", "sector": "Industrials"},
    {"ticker": "PC1", "sector": "Industrials"},
    {"ticker": "GAS", "sector": "Energy"},
    {"ticker": "PLX", "sector": "Energy"},
    {"ticker": "POW", "sector": "Energy"},
    {"ticker": "REE", "sector": "Energy"},
    {"ticker": "NT2", "sector": "Energy"},
    {"ticker": "FPT", "sector": "Technology"},
    {"ticker": "CTR", "sector": "Technology"},
    {"ticker": "VJC", "sector": "Transport"},
    {"ticker": "HVN", "sector": "Transport"},
    {"ticker": "GMD", "sector": "Transport"},
    {"ticker": "HAG", "sector": "Agriculture"},
    {"ticker": "VHC", "sector": "Agriculture"},
    {"ticker": "ANV", "sector": "Agriculture"},
]
SECTOR_BY_TICKER = {u["ticker"]: u["sector"] for u in UNIVERSE}

LOOKBACK_DAYS = 1095  # ~3 years -- enough for the walk-forward backtest to span multiple regimes
TOP_N_PICKS = 8
MIN_COMPLETE_ROWS_FOR_VIF = 10  # below this, a VIF-based factor-pruning decision is unreliable
MIN_SECTOR_GROUP_SIZE = 4  # sectors smaller than this fall back to global (cross-sector) z-scores
MOMENTUM_LOOKBACK_DAYS = 252
MOMENTUM_SKIP_DAYS = 21
WALK_FORWARD_FOLDS = 5
WALK_FORWARD_MIN_TRAIN_DAYS = 120
FOREIGN_FLOW_HISTORY_PATH = Path(__file__).resolve().parents[2] / "data" / "foreign_flow_history.json"
FOREIGN_FLOW_HISTORY_TRIM_DAYS = 30
FOREIGN_FLOW_FACTOR_WINDOW = 5
# vnstock's free-tier rate limiter was observed live to kill the whole Python
# process with SystemExit (not a catchable Exception) after ~10 tickers'
# worth of calls in well under a minute. This pacing plus the SystemExit
# handling in `_safe_fetch` are both required, not just one or the other.
FETCH_PAUSE_SECONDS = 3.5

HIGHER_IS_BETTER = {
    "earnings_yield": True,
    "book_to_market": True,
    "roic": True,
    "cfo_to_assets": True,
    "ev_to_ebitda": False,
    "momentum": True,
    "foreign_flow_5d": True,
}


def _sanitize(obj):
    """Recursively convert numpy scalars to native types and NaN/Inf to None --
    plain json.dumps would otherwise emit a bare `NaN` token, which is not
    valid JSON and browsers' JSON.parse rejects it.
    """
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if (np.isnan(v) or np.isinf(v)) else v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, date, datetime)):
        return str(obj)
    return obj


def _safe_fetch(description: str, fn, *args, **kwargs):
    """Run a vnstock call, tolerating both normal exceptions and the
    rate-limiter's SystemExit (verified live: it does not raise a catchable
    Exception, it calls something equivalent to sys.exit()). Returns
    (result, hit_rate_limit).
    """
    try:
        return fn(*args, **kwargs), False
    except SystemExit:
        log.warning("Rate limit hit while fetching %s -- stopping further fetches this run", description)
        return None, True
    except Exception:
        log.exception("Fetch failed for %s", description)
        return None, False


def fetch_universe_data(tickers: list[str]) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()

    ohlcv_by_ticker: dict[str, pd.DataFrame] = {}
    fundamentals_by_ticker: dict[str, dict] = {}

    for ticker in tickers:
        ohlcv, rate_limited = _safe_fetch(f"OHLCV/{ticker}", vnstock_client.get_ohlcv, ticker, start=start, end=end)
        if rate_limited:
            break
        if ohlcv is not None:
            ohlcv_by_ticker[ticker] = ohlcv
            log.info("OHLCV OK for %s (%d rows)", ticker, len(ohlcv))
        time.sleep(FETCH_PAUSE_SECONDS)

        fundamentals, rate_limited = _safe_fetch(f"fundamentals/{ticker}", vnstock_client.get_fundamentals, ticker)
        if rate_limited:
            break
        if fundamentals is not None:
            fundamentals_by_ticker[ticker] = fundamentals
        time.sleep(FETCH_PAUSE_SECONDS)

    if len(ohlcv_by_ticker) < len(tickers):
        log.warning(
            "Only fetched %d/%d tickers this run (rate limit or transient failures) -- "
            "snapshot will cover a smaller universe than usual, not the full curated list.",
            len(ohlcv_by_ticker), len(tickers),
        )

    return ohlcv_by_ticker, fundamentals_by_ticker


def fetch_foreign_flow_snapshots(tickers: list[str]) -> dict[str, float]:
    """Live today-snapshot of foreign net-buy value per ticker (see
    vnstock_client.get_foreign_net_value). Paced and rate-limit-tolerant the
    same way as fetch_universe_data -- this is a THIRD call per ticker on top
    of OHLCV + fundamentals, so it adds real runtime; stops early rather than
    crash if the rate limit is hit partway through.
    """
    snapshots: dict[str, float] = {}
    for ticker in tickers:
        value, rate_limited = _safe_fetch(f"foreign-flow/{ticker}", vnstock_client.get_foreign_net_value, ticker)
        if rate_limited:
            break
        if value is not None:
            snapshots[ticker] = value
        time.sleep(FETCH_PAUSE_SECONDS)
    return snapshots


def load_foreign_flow_history(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def update_foreign_flow_history(
    history: dict[str, list[dict]],
    snapshot_by_ticker: dict[str, float | None],
    today: str,
    trim_days: int = FOREIGN_FLOW_HISTORY_TRIM_DAYS,
) -> dict[str, list[dict]]:
    """Upserts today's snapshot into each ticker's history -- one point per
    calendar day, so re-running this multiple times on the same day (as the
    hourly cron does) updates today's entry rather than duplicating it --
    then trims to the most recent `trim_days` entries per ticker.
    """
    updated = {k: list(v) for k, v in history.items()}
    for ticker, net_value in snapshot_by_ticker.items():
        if net_value is None:
            continue
        series = updated.setdefault(ticker, [])
        idx = next((i for i, p in enumerate(series) if p["date"] == today), None)
        if idx is not None:
            series[idx] = {"date": today, "net_value": net_value}
        else:
            series.append({"date": today, "net_value": net_value})
        series.sort(key=lambda p: p["date"])
        updated[ticker] = series[-trim_days:]
    return updated


def compute_foreign_flow_factor(history: dict[str, list[dict]], window: int = FOREIGN_FLOW_FACTOR_WINDOW) -> dict[str, float]:
    """Rolling sum of the last `window` available days' net foreign-buy value
    per ticker. Builds up gradually -- with only 1 day of history recorded so
    far, this is just that one day's value, not a real multi-day trend yet.
    """
    result = {}
    for ticker, series in history.items():
        recent = series[-window:]
        if recent:
            result[ticker] = sum(p["net_value"] for p in recent)
    return result


def build_returns_frame(ohlcv_by_ticker: dict[str, pd.DataFrame]) -> pd.DataFrame:
    closes = {}
    for ticker, df in ohlcv_by_ticker.items():
        if df is None or df.empty:
            continue
        closes[ticker] = df.set_index("time")["close"]
    price_df = pd.DataFrame(closes).sort_index().ffill()
    return price_df.pct_change().dropna(how="all")


def screen(
    fundamentals_by_ticker: dict[str, dict],
    momentum_by_ticker: dict[str, float],
    foreign_flow_by_ticker: dict[str, float],
) -> tuple[pd.DataFrame, list[str]]:
    """Score every fetched, non-disqualified ticker -- including financials,
    scored from whichever factors they actually have. Returns (df with one
    row per fetched ticker, list of VIF-dropped factors). Disqualified and
    factor-less rows are included with composite_score=NaN, not silently
    excluded, so the rankings table can show them plainly.
    """
    rows = []
    for ticker, f in fundamentals_by_ticker.items():
        if not f:
            continue
        check = GovernanceCheckInput(
            auditor_opinion="UNQUALIFIED",  # not available from vnstock -- assumed clean, see module docstring
            filing_on_time=True,
            warning_status="NONE",
            margin_eligible=True,
            # A missing interest_coverage is NOT the same as a failing one -- verified
            # live, KBS simply doesn't report this ratio for banks (their accounting
            # doesn't have a comparable EBIT/interest-expense figure). Missing -> not
            # evaluated, not failed.
            min_interest_coverage_ok=(f.get("interest_coverage") is None) or (f["interest_coverage"] >= 3.0),
        )
        disq, reasons = governance.is_disqualified(check)
        rows.append({"ticker": ticker, "sector": SECTOR_BY_TICKER.get(ticker, "Other"), "disqualified": disq, "reasons": reasons, **f})

    df = pd.DataFrame(rows)
    if df.empty:
        return df, []

    df["momentum"] = df["ticker"].map(momentum_by_ticker)
    df["foreign_flow_5d"] = df["ticker"].map(foreign_flow_by_ticker)

    factor_cols = list(HIGHER_IS_BETTER.keys())
    df[factor_cols] = df[factor_cols].apply(pd.to_numeric, errors="coerce")
    df["factors_used_count"] = df[factor_cols].notna().sum(axis=1)

    eligible = df[~df["disqualified"]]
    complete = eligible[factor_cols].dropna()
    if len(complete) >= MIN_COMPLETE_ROWS_FOR_VIF:
        pruned, dropped = diagnostics.prune_by_vif(complete)
        surviving_cols = list(pruned.columns) if len(pruned.columns) else factor_cols
    else:
        surviving_cols, dropped = factor_cols, []

    weights = {k: v for k, v in HIGHER_IS_BETTER.items() if k in surviving_cols}
    df["composite_score"] = np.nan
    df.loc[~df["disqualified"], "composite_score"] = factors.sector_neutral_composite_score(
        eligible, weights, sector_col="sector", min_group_size=MIN_SECTOR_GROUP_SIZE
    )
    df["percentile_rank"] = df["composite_score"].rank(pct=True) * 100
    df["vif_dropped_factors"] = [dropped] * len(df)
    return df.sort_values("composite_score", ascending=False, na_position="last"), dropped


def build_picks(
    scored: pd.DataFrame,
    returns_df: pd.DataFrame,
    top_n: int = TOP_N_PICKS,
) -> tuple[list[dict], dict, list[str], pd.Series | None]:
    scoreable = scored[scored["composite_score"].notna()]
    top = scoreable.head(top_n).copy()
    tickers = [t for t in top["ticker"] if t in returns_df.columns]
    if not tickers:
        return [], {}, [], None

    top_indexed = top.set_index("ticker")
    shortlist_returns = returns_df[tickers]

    # "Today's" live weights use ALL available history (most current
    # information) -- the walk-forward evaluation below tests how this SAME
    # methodology would have performed historically; it doesn't hold back
    # recent data from the live recommendation itself.
    trailing_total_return = (1 + shortlist_returns).prod() - 1
    ic = grinold.information_coefficient(top_indexed["composite_score"], trailing_total_return)
    sigma = shortlist_returns.std() * np.sqrt(252)
    score_z = factors.zscore(top_indexed["composite_score"])
    mu = grinold.expected_active_return(ic, sigma, score_z)
    cov = shortlist_returns.cov().values * 252
    weights = optimizer.max_sharpe_weights(mu.values, cov)

    wf = backtest.walk_forward_evaluate(
        shortlist_returns, tickers, score_z, n_folds=WALK_FORWARD_FOLDS, min_train_days=WALK_FORWARD_MIN_TRAIN_DAYS
    )
    if wf is not None:
        wf_returns = wf.pop("combined_returns")
        # Sampled from the FULL universe (returns_df), not just the 8-name
        # shortlist -- comparing the shortlist against random baskets drawn
        # from itself would be meaningless.
        bt_compare = backtest.compare_against_alternatives(
            returns_df.iloc[-len(wf_returns):], tickers, list(returns_df.columns), n_trials=300
        )
        backtest_summary = {
            "method": "walk-forward (expanding-window re-optimization, folds concatenated)",
            "walk_forward_sharpe": wf["combined_sharpe"],
            "walk_forward_cumulative_return": wf["combined_cumulative_return"],
            "walk_forward_max_drawdown": wf["combined_max_drawdown"],
            "walk_forward_n_folds": wf["n_folds"],
            "walk_forward_fold_summaries": wf["fold_summaries"],
            "vs_random_baskets_percentile": bt_compare.get("percentile_rank"),
        }
        sharpe_for_display = wf["combined_sharpe"]
    else:
        # Not enough history to walk forward (e.g. a brand-new ticker) -- fall
        # back to a plain full-window backtest rather than omitting a number.
        bt = backtest.walk_forward_backtest(shortlist_returns, tickers, weights)
        backtest_summary = {
            "method": "single-window (insufficient history to walk forward)",
            **bt,
            "vs_random_baskets_percentile": None,
        }
        sharpe_for_display = bt["sharpe_ratio"]
        wf_returns = None

    # The max-Sharpe optimizer can legitimately allocate ~0% to a shortlisted
    # name (verified live: 5 of 8 shortlisted names got weights on the order
    # of 1e-17 given this basket's real covariance structure). Showing those
    # as "picks" to approve would be misleading -- only surface names the
    # optimizer actually wants a position in.
    MIN_DISPLAYED_WEIGHT = 0.01
    picks = []
    for i, ticker in enumerate(tickers):
        if weights[i] < MIN_DISPLAYED_WEIGHT:
            continue
        row = top_indexed.loc[ticker]
        picks.append(
            {
                "id": len(picks) + 1,
                "asset_id": len(picks) + 1,
                "ticker": ticker,
                "company_name": ticker,
                "pick_date": date.today().isoformat(),
                "rationale": (
                    f"Sector-neutral composite score at {ordinal(round(row['percentile_rank']))} percentile "
                    f"among {len(scoreable)} scoreable tickers. In-sample rank-IC vs trailing "
                    f"return: {ic:.2f}. Expected active return (Grinold): {mu[ticker]:.4f}."
                ),
                "projected_sharpe": sharpe_for_display,
                "suggested_weight": float(weights[i]),
                "backtest_summary": backtest_summary,
                "status": "PENDING",
                "decided_at": None,
                "decided_by": None,
            }
        )
    kept_tickers = [p["ticker"] for p in picks]
    return picks, backtest_summary, kept_tickers, wf_returns


def build_flow_signals(ohlcv_by_ticker: dict[str, pd.DataFrame]) -> dict[str, order_flow.FlowSignal]:
    """One signal per ticker with enough history -- ALL of them, not just anomalies.
    Used both for the rankings table (every row gets a volume column) and,
    filtered to `is_anomalous`, for the "Unusual Buying Activity" panel. This
    is the VOLUME-anomaly signal, distinct from the foreign_flow ownership factor.
    """
    signals: dict[str, order_flow.FlowSignal] = {}
    for ticker, df in ohlcv_by_ticker.items():
        if df is None or df.empty:
            continue
        sig = order_flow.detect_flow_signal(df["time"], df["close"], df["volume"])
        if sig is not None:
            signals[ticker] = sig
    return signals


def build_flow_alerts(flow_signals: dict[str, order_flow.FlowSignal]) -> list[dict]:
    alerts = []
    anomalous = [(ticker, sig) for ticker, sig in flow_signals.items() if sig.is_anomalous]
    for i, (ticker, sig) in enumerate(anomalous):
        alerts.append(
            {
                "id": i + 1,
                "asset_id": i + 1,
                "ticker": ticker,
                "as_of_date": str(pd.Timestamp(sig.as_of).date()),
                "relative_volume": sig.relative_volume,
                "volume_zscore": sig.volume_zscore,
                "price_change_pct": sig.price_change_pct,
                "direction": sig.direction,
                "foreign_net_value": sig.foreign_net_value,
                "is_anomalous": sig.is_anomalous,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return alerts


def build_rankings(
    scored: pd.DataFrame,
    flow_signals: dict[str, order_flow.FlowSignal],
    ohlcv_by_ticker: dict[str, pd.DataFrame],
    foreign_net_value_today: dict[str, float],
) -> list[dict]:
    """One row per fetched ticker -- the full "rank everything" table, not just
    a shortlist. Disqualified/low-data rows are included (composite_score is
    null), not hidden, so the table is honest about coverage.
    """
    rows = []
    for _, r in scored.iterrows():
        ticker = r["ticker"]
        df = ohlcv_by_ticker.get(ticker)
        # vnstock's Quote.history() reports `close` in THOUSANDS of VND (verified
        # live) -- converted to whole VND here so it's not silently 1000x off.
        last_price = float(df["close"].iloc[-1]) * 1000 if df is not None and not df.empty else None
        sig = flow_signals.get(ticker)
        rows.append(
            {
                "ticker": ticker,
                "sector": r["sector"],
                "disqualified": bool(r["disqualified"]),
                "disqualification_reasons": r["reasons"],
                "composite_score": r["composite_score"],
                "percentile_rank": r["percentile_rank"],
                "factors_used_count": int(r["factors_used_count"]),
                "earnings_yield": r["earnings_yield"],
                "book_to_market": r["book_to_market"],
                "ev_to_ebitda": r["ev_to_ebitda"],
                "roic": r["roic"],
                "cfo_to_assets": r["cfo_to_assets"],
                "interest_coverage": r["interest_coverage"],
                "momentum": r["momentum"],
                "foreign_flow_5d": r["foreign_flow_5d"],
                "foreign_net_value_today": foreign_net_value_today.get(ticker),
                "last_price": last_price,
                "price_change_pct": sig.price_change_pct if sig else None,
                "relative_volume": sig.relative_volume if sig else None,
                "volume_zscore": sig.volume_zscore if sig else None,
                "flow_direction": sig.direction if sig else None,
            }
        )
    return rows


def build_performance_series(
    walk_forward_returns: pd.Series | None,
    final_factor_exposures: dict,
    final_diagnostics: dict,
) -> list[dict]:
    """Equity curve from the walk-forward COMBINED out-of-sample returns (each
    fold's own re-optimized weights applied to that fold's held-out period,
    concatenated) -- a genuine multi-regime performance history, not a single
    static split replayed with one fixed weight vector.
    """
    if walk_forward_returns is None or walk_forward_returns.empty:
        return []
    nav = 1_000_000_000 * (1 + walk_forward_returns).cumprod()
    # `backtest.drawdown_series` correctly anchors day 1's drawdown against the
    # starting capital (not trivially 0 -- see its docstring for why that
    # matters). `.cummin()` on top turns "today's drawdown" into "the WORST
    # drawdown seen up to and including today", which is what a per-day
    # "max_drawdown" field should mean -- verified live, the naive version
    # showed -4.5% on the last day while the actual worst point in the same
    # walk-forward run was -19.2%.
    running_max_drawdown = backtest.drawdown_series(walk_forward_returns).cummin()

    MIN_OBS_FOR_SHARPE = 20  # fewer points than this makes an annualized Sharpe pure noise
    snapshots = []
    for i, (ts, value) in enumerate(nav.items()):
        is_last = i == len(nav) - 1
        snapshots.append(
            {
                "id": i + 1,
                "snapshot_date": str(pd.Timestamp(ts).date()) if hasattr(ts, "date") else str(ts),
                "nav": float(value),
                "sharpe_ratio": backtest.annualized_sharpe(walk_forward_returns.iloc[: i + 1]) if i + 1 >= MIN_OBS_FOR_SHARPE else None,
                "max_drawdown": float(running_max_drawdown.iloc[i]),
                "factor_exposures": final_factor_exposures if is_last else {},
                "diagnostics": final_diagnostics if is_last else {},
            }
        )
    return snapshots


def main(out_dir: Path) -> int:
    tickers = [u["ticker"] for u in UNIVERSE]
    log.info("Fetching live data for %d curated tickers...", len(tickers))
    ohlcv_by_ticker, fundamentals_by_ticker = fetch_universe_data(tickers)
    returns_df = build_returns_frame(ohlcv_by_ticker)
    log.info("Returns frame: %d trading days", len(returns_df))

    momentum_by_ticker = factors.momentum_12_1(
        returns_df, lookback_days=MOMENTUM_LOOKBACK_DAYS, skip_days=MOMENTUM_SKIP_DAYS
    ).to_dict()

    log.info("Fetching live foreign-flow snapshots...")
    foreign_net_value_today = fetch_foreign_flow_snapshots(list(ohlcv_by_ticker.keys()))
    foreign_flow_history = load_foreign_flow_history(FOREIGN_FLOW_HISTORY_PATH)
    today_str = date.today().isoformat()
    foreign_flow_history = update_foreign_flow_history(foreign_flow_history, foreign_net_value_today, today_str)
    foreign_flow_5d_by_ticker = compute_foreign_flow_factor(foreign_flow_history, window=FOREIGN_FLOW_FACTOR_WINDOW)
    FOREIGN_FLOW_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    FOREIGN_FLOW_HISTORY_PATH.write_text(json.dumps(_sanitize(foreign_flow_history), indent=2))

    scored, vif_dropped = screen(fundamentals_by_ticker, momentum_by_ticker, foreign_flow_5d_by_ticker)
    picks, backtest_summary, pick_tickers, wf_returns = (
        build_picks(scored, returns_df) if not scored.empty else ([], {}, [], None)
    )
    flow_signals = build_flow_signals(ohlcv_by_ticker)
    flow_alerts = build_flow_alerts(flow_signals)
    rankings = build_rankings(scored, flow_signals, ohlcv_by_ticker, foreign_net_value_today) if not scored.empty else []

    final_factor_exposures = (
        {k: float(factors.zscore(scored[k]).loc[scored["ticker"].isin(pick_tickers)].mean()) for k in HIGHER_IS_BETTER}
        if picks
        else {}
    )
    final_diagnostics = {}
    if not scored.empty and pick_tickers:
        factor_cols = list(HIGHER_IS_BETTER.keys())
        forward_return_proxy = (1 + returns_df[pick_tickers].tail(60)).prod() - 1
        indexed = scored.set_index("ticker")
        final_diagnostics = diagnostics.run_factor_regression_diagnostics(
            indexed.loc[pick_tickers, factor_cols],
            forward_return_proxy,
        )

    performance = build_performance_series(wf_returns, final_factor_exposures, final_diagnostics)

    disqualified_count = int(scored["disqualified"].sum()) if not scored.empty else 0
    scoreable_count = int(scored["composite_score"].notna().sum()) if not scored.empty else 0

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "picks.json").write_text(json.dumps(_sanitize(picks), indent=2))
    (out_dir / "rankings.json").write_text(json.dumps(_sanitize(rankings), indent=2))
    (out_dir / "flow_alerts.json").write_text(json.dumps(_sanitize(flow_alerts), indent=2))
    (out_dir / "performance.json").write_text(json.dumps(_sanitize(performance), indent=2))
    (out_dir / "holdings.json").write_text(json.dumps([], indent=2))
    (out_dir / "meta.json").write_text(
        json.dumps(
            _sanitize(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "universe": tickers,
                    "universe_size": len(tickers),
                    "fetched_count": len(ohlcv_by_ticker),
                    "scoreable_count": scoreable_count,
                    "disqualified_count": disqualified_count,
                    "vif_dropped_factors": vif_dropped,
                    "factors": list(HIGHER_IS_BETTER.keys()),
                    "walk_forward_folds": backtest_summary.get("walk_forward_n_folds"),
                    "foreign_flow_history_days": max((len(v) for v in foreign_flow_history.values()), default=0),
                    "note": (
                        "~60 hand-picked liquid HOSE large/mid caps across sectors, not the "
                        "full ~723-ticker universe (vnstock's free-tier rate limit makes "
                        "covering the full market impractical for an hourly refresh). Scoring "
                        "is sector-neutral (a bank is compared to other financials, not to "
                        "real estate). Factors include 12-1 month momentum and a rolling "
                        "foreign-flow signal that builds up over time (see "
                        "foreign_flow_history_days). Governance fields are assumed clean, not "
                        "verified against real HOSE disclosures. The shortlist backtest is "
                        "walk-forward across multiple historical folds, not a single split."
                    ),
                }
            ),
            indent=2,
        )
    )

    log.info(
        "Wrote snapshot: %d picks, %d ranked rows, %d flow alerts, %d performance points, %d disqualified",
        len(picks), len(rankings), len(flow_alerts), len(performance), disqualified_count,
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, default="../frontend/public/data")
    args = parser.parse_args()
    raise SystemExit(main(Path(args.out)))
