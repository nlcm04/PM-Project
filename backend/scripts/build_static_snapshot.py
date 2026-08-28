"""Generate a static, real-data JSON snapshot for the GitHub Pages demo.

GitHub Pages only serves static files, so this runs the real screening +
backtest pipeline in-memory against live vnstock data -- no database
required -- and writes plain JSON that the static frontend fetches directly.
Everything numeric here comes from a real vnstock pull; nothing is fabricated.

Deliberate scope limits, stated here rather than hidden:

1. Curated, non-financial universe only (see UNIVERSE below), not the full
   ~723-ticker HOSE listing. Two reasons: (a) the value/quality factor set
   (ROIC, EV/EBITDA, CFO/Assets) doesn't apply to banks/brokers' accounting --
   a live pull showed ACB returning None for exactly these fields -- so
   financials are excluded rather than silently mis-scored; (b) pulling ~700
   tickers per run against a free, scraping-based API on every CI run isn't a
   considerate load, so this stays to a fixed blue-chip list.
2. Governance fields (auditor opinion, filing status, HOSE warning list) are
   NOT available from vnstock (see app/data/vnstock_client.py). Every ticker
   here is assumed governance-clean because it's a hand-picked large-cap
   list, not because it was actually checked against HOSE disclosures.
3. Out-of-sample split to avoid look-ahead bias: expected returns, the
   covariance matrix, and portfolio weights are computed on the FIRST ~70%
   of the lookback window; Sharpe, drawdown, the equity curve, and the
   vs-random-baskets comparison are all evaluated on the LAST ~30%, which
   the weight computation never sees. Testing a portfolio on the same window
   used to build it would inflate the numbers -- this doesn't.
4. The Grinold IC is a rank-correlation between today's composite score and
   each stock's realized return over the in-sample window -- a rough
   diagnostic, not a validated forward-predictive IC, since point-in-time
   historical fundamentals aren't available to test true predictiveness.
5. "Portfolio Health" shows the backtested equity curve of today's screened
   basket, not a real brokerage account -- nothing has actually been bought.
   holdings.json is intentionally empty.

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

# Hand-picked liquid HOSE large caps, non-financial only (see docstring point 1).
UNIVERSE = [
    "VNM", "VIC", "VHM", "HPG", "FPT", "MWG", "MSN", "GAS", "PLX", "POW",
    "VRE", "DGC", "DPM", "GVR", "KDH", "NVL", "PNJ", "REE", "SAB", "VJC",
]
LOOKBACK_DAYS = 400
IN_SAMPLE_FRACTION = 0.7
TOP_N_PICKS = 8
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


def build_returns_frame(ohlcv_by_ticker: dict[str, pd.DataFrame]) -> pd.DataFrame:
    closes = {}
    for ticker, df in ohlcv_by_ticker.items():
        if df is None or df.empty:
            continue
        closes[ticker] = df.set_index("time")["close"]
    price_df = pd.DataFrame(closes).sort_index().ffill()
    return price_df.pct_change().dropna(how="all")


def split_in_out_sample(returns_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_idx = int(len(returns_df) * IN_SAMPLE_FRACTION)
    return returns_df.iloc[:split_idx], returns_df.iloc[split_idx:]


def screen(fundamentals_by_ticker: dict[str, dict]) -> tuple[pd.DataFrame, list[str]]:
    rows = []
    for ticker, f in fundamentals_by_ticker.items():
        if not f:
            continue
        check = GovernanceCheckInput(
            auditor_opinion="UNQUALIFIED",  # not available from vnstock -- assumed clean, see docstring point 2
            filing_on_time=True,
            warning_status="NONE",
            margin_eligible=True,
            min_interest_coverage_ok=(f.get("interest_coverage") or 0) >= 3.0,
        )
        disq, reasons = governance.is_disqualified(check)
        rows.append({"ticker": ticker, "disqualified": disq, "reasons": reasons, **f})

    df = pd.DataFrame(rows)
    if df.empty:
        return df, []

    eligible = df[~df["disqualified"]].copy()
    factor_cols = list(HIGHER_IS_BETTER.keys())
    numeric = eligible[factor_cols].apply(pd.to_numeric, errors="coerce")
    complete_mask = numeric.notna().all(axis=1)
    excluded_missing_data = eligible.loc[~complete_mask, "ticker"].tolist()
    usable = eligible.loc[complete_mask].copy()
    if usable.empty:
        return usable, excluded_missing_data

    pruned, dropped = diagnostics.prune_by_vif(numeric.loc[complete_mask])
    weights = {k: v for k, v in HIGHER_IS_BETTER.items() if k in pruned.columns}
    usable["composite_score"] = factors.composite_score(usable, weights)
    usable["percentile_rank"] = usable["composite_score"].rank(pct=True) * 100
    usable["vif_dropped_factors"] = [dropped] * len(usable)
    return usable.sort_values("composite_score", ascending=False), excluded_missing_data


def build_picks(
    scored: pd.DataFrame,
    in_sample: pd.DataFrame,
    out_sample: pd.DataFrame,
    top_n: int = TOP_N_PICKS,
) -> tuple[list[dict], dict, list[str]]:
    top = scored.head(top_n).copy()
    tickers = [t for t in top["ticker"] if t in in_sample.columns and t in out_sample.columns]
    if not tickers:
        return [], {}, []

    top_indexed = top.set_index("ticker")
    trailing_total_return = (1 + in_sample[tickers]).prod() - 1
    ic = grinold.information_coefficient(top_indexed.loc[tickers, "composite_score"], trailing_total_return)

    sigma = in_sample[tickers].std() * np.sqrt(252)
    score_z = factors.zscore(top_indexed.loc[tickers, "composite_score"])
    mu = grinold.expected_active_return(ic, sigma, score_z)

    cov = in_sample[tickers].cov().values * 252
    weights = optimizer.max_sharpe_weights(mu.values, cov)

    # Evaluated OUT of sample -- see docstring point 3. Computed on the full
    # shortlist (including any near-zero optimizer weights) so the portfolio
    # math matches what the optimizer actually produced.
    bt = backtest.walk_forward_backtest(out_sample, tickers, weights)
    bt_compare = backtest.compare_against_alternatives(out_sample, tickers, list(out_sample.columns), n_trials=300)
    backtest_summary = {**bt, "vs_random_baskets_percentile": bt_compare.get("percentile_rank")}

    # The max-Sharpe optimizer can legitimately allocate ~0% to a shortlisted
    # name (verified live: 5 of 8 shortlisted names got weights on the order
    # of 1e-17 given this basket's real covariance structure). Showing those
    # as "picks" to approve would be misleading -- only surface names the
    # optimizer actually wants a position in.
    MIN_DISPLAYED_WEIGHT = 0.01
    picks = []
    kept_tickers = []
    for i, ticker in enumerate(tickers):
        if weights[i] < MIN_DISPLAYED_WEIGHT:
            continue
        kept_tickers.append(ticker)
        row = top_indexed.loc[ticker]
        picks.append(
            {
                "id": len(picks) + 1,
                "asset_id": len(picks) + 1,
                "ticker": ticker,
                "company_name": ticker,
                "pick_date": date.today().isoformat(),
                "rationale": (
                    f"Composite score at {ordinal(round(row['percentile_rank']))} percentile "
                    f"among {len(scored)} screened tickers. In-sample rank-IC vs trailing "
                    f"return: {ic:.2f}. Expected active return (Grinold): {mu[ticker]:.4f}."
                ),
                "projected_sharpe": bt["sharpe_ratio"],
                "suggested_weight": float(weights[i]),
                "backtest_summary": backtest_summary,
                "status": "PENDING",
                "decided_at": None,
                "decided_by": None,
            }
        )
    return picks, backtest_summary, kept_tickers


def build_flow_alerts(ohlcv_by_ticker: dict[str, pd.DataFrame]) -> list[dict]:
    alerts = []
    for i, (ticker, df) in enumerate(ohlcv_by_ticker.items()):
        if df is None or df.empty:
            continue
        sig = order_flow.detect_flow_signal(df["time"], df["close"], df["volume"])
        if sig and sig.is_anomalous:
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


def build_performance_series(
    out_sample: pd.DataFrame,
    tickers: list[str],
    weights: np.ndarray,
    final_factor_exposures: dict,
    final_diagnostics: dict,
) -> list[dict]:
    if not tickers:
        return []
    port_returns = out_sample[tickers] @ weights
    nav = 1_000_000_000 * (1 + port_returns).cumprod()
    running_max = nav.cummax()
    drawdown = nav / running_max - 1

    MIN_OBS_FOR_SHARPE = 20  # fewer points than this makes an annualized Sharpe pure noise (e.g. -30 on day 2)
    snapshots = []
    for i, (ts, value) in enumerate(nav.items()):
        is_last = i == len(nav) - 1
        snapshots.append(
            {
                "id": i + 1,
                "snapshot_date": str(pd.Timestamp(ts).date()),
                "nav": float(value),
                "sharpe_ratio": backtest.annualized_sharpe(port_returns.iloc[: i + 1]) if i + 1 >= MIN_OBS_FOR_SHARPE else None,
                "max_drawdown": float(drawdown.iloc[i]),
                "factor_exposures": final_factor_exposures if is_last else {},
                "diagnostics": final_diagnostics if is_last else {},
            }
        )
    return snapshots


def main(out_dir: Path) -> int:
    log.info("Fetching live data for %d curated tickers...", len(UNIVERSE))
    ohlcv_by_ticker, fundamentals_by_ticker = fetch_universe_data(UNIVERSE)
    returns_df = build_returns_frame(ohlcv_by_ticker)
    in_sample, out_sample = split_in_out_sample(returns_df)
    log.info("Returns frame: %d trading days (%d in-sample, %d out-of-sample)", len(returns_df), len(in_sample), len(out_sample))

    scored, excluded_missing_data = screen(fundamentals_by_ticker)
    picks, backtest_summary, pick_tickers = (
        build_picks(scored, in_sample, out_sample) if not scored.empty else ([], {}, [])
    )
    flow_alerts = build_flow_alerts(ohlcv_by_ticker)

    weights = np.array([p["suggested_weight"] for p in picks]) if picks else np.array([])
    final_factor_exposures = (
        {k: float(factors.zscore(scored[k]).loc[scored["ticker"].isin(pick_tickers)].mean()) for k in HIGHER_IS_BETTER}
        if picks
        else {}
    )
    final_diagnostics = {}
    if not scored.empty and pick_tickers:
        factor_cols = list(HIGHER_IS_BETTER.keys())
        forward_return_proxy = (1 + out_sample[pick_tickers]).prod() - 1
        indexed = scored.set_index("ticker")
        final_diagnostics = diagnostics.run_factor_regression_diagnostics(
            indexed.loc[pick_tickers, factor_cols].apply(pd.to_numeric, errors="coerce"),
            forward_return_proxy,
        )

    performance = build_performance_series(out_sample, pick_tickers, weights, final_factor_exposures, final_diagnostics)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "picks.json").write_text(json.dumps(_sanitize(picks), indent=2))
    (out_dir / "flow_alerts.json").write_text(json.dumps(_sanitize(flow_alerts), indent=2))
    (out_dir / "performance.json").write_text(json.dumps(_sanitize(performance), indent=2))
    (out_dir / "holdings.json").write_text(json.dumps([], indent=2))
    (out_dir / "meta.json").write_text(
        json.dumps(
            _sanitize(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "universe": UNIVERSE,
                    "universe_size": len(UNIVERSE),
                    "fetched_count": len(ohlcv_by_ticker),
                    "screened_count": len(scored),
                    "excluded_missing_fundamentals": excluded_missing_data,
                    "in_sample_days": len(in_sample),
                    "out_of_sample_days": len(out_sample),
                    "note": (
                        "Hand-picked non-financial HOSE blue-chip tickers, not the full "
                        "~723-ticker universe. Governance fields are assumed clean, not "
                        "verified against real HOSE disclosures. Backtest is evaluated "
                        "out-of-sample (see script docstring)."
                    ),
                }
            ),
            indent=2,
        )
    )

    log.info(
        "Wrote snapshot: %d picks, %d flow alerts, %d performance points, %d excluded for missing data",
        len(picks), len(flow_alerts), len(performance), len(excluded_missing_data),
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, default="../frontend/public/data")
    args = parser.parse_args()
    raise SystemExit(main(Path(args.out)))
