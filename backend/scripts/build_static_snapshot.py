"""Generate a static, real-data JSON snapshot for the GitHub Pages demo.

GitHub Pages only serves static files, so this runs the real screening +
backtest pipeline in-memory against live vnstock data -- no database
required -- and writes plain JSON that the static frontend fetches directly.
Everything numeric here comes from a real vnstock pull; nothing is fabricated.

Deliberate scope limits, stated here rather than hidden:

1. ~60 hand-picked liquid HOSE large/mid caps across sectors (see UNIVERSE
   below), not the full ~723-ticker HOSE listing. vnstock's free-tier rate
   limiter was observed live to kill the whole Python process with
   SystemExit (not a catchable Exception) after roughly 10 tickers' worth of
   calls when made too fast -- pulling the full universe every run, at a
   pace that avoids that, would take well over an hour and defeat the point
   of a near-real-time refresh. 60 names paced at 3.5s/call takes roughly
   10-15 minutes, which fits an hourly refresh during HOSE trading hours.
2. Financial-sector tickers (banks, brokers) ARE included, but the
   ROIC/EV-EBITDA/CFO-based factors don't apply to their accounting -- a
   live pull showed ACB returning None for exactly those fields. Rather
   than exclude financials outright, each ticker's composite score is
   computed from whichever of the 5 factors it actually has data for
   (see `factors_used_count` in rankings.json); a bank typically scores off
   just earnings_yield/book_to_market (2 of 5), which is disclosed per-row,
   not hidden.
3. Governance fields (auditor opinion, filing status, HOSE warning list) are
   NOT available from vnstock (see app/data/vnstock_client.py). Every
   ticker here is assumed governance-clean because it's a hand-picked
   large/mid-cap list, not because it was actually checked against HOSE
   disclosures.
4. Out-of-sample split to avoid look-ahead bias: expected returns, the
   covariance matrix, and portfolio weights (for the small top-N "picks"
   shortlist) are computed on the FIRST ~70% of the lookback window; Sharpe,
   drawdown, the equity curve, and the vs-random-baskets comparison are all
   evaluated on the LAST ~30%, which the weight computation never sees.
5. The Grinold IC is a rank-correlation between today's composite score and
   each stock's realized return over the in-sample window -- a rough
   diagnostic, not a validated forward-predictive IC, since point-in-time
   historical fundamentals aren't available to test true predictiveness.
6. "Portfolio Health" (in the default, no-user-portfolio state) shows the
   backtested equity curve of the top-N shortlist, not a real brokerage
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

# ~60 liquid HOSE large/mid caps spanning most sectors, incl. financials
# (see docstring point 2 for how those are scored). Hand-picked from public
# knowledge of well-known HOSE tickers, not pulled from a live listing --
# a wrong/delisted symbol here just fails its own fetch (logged, skipped),
# it doesn't break the run.
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

LOOKBACK_DAYS = 400
IN_SAMPLE_FRACTION = 0.7
TOP_N_PICKS = 8
MIN_COMPLETE_ROWS_FOR_VIF = 10  # below this, a VIF-based factor-pruning decision is unreliable
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
    """Score every fetched, non-disqualified ticker -- including financials,
    scored from whichever factors they actually have (see docstring point 2).
    Returns (df with one row per fetched ticker, list of VIF-dropped factors).
    Disqualified and factor-less rows are included with composite_score=NaN,
    not silently excluded, so the rankings table can show them plainly.
    """
    rows = []
    for ticker, f in fundamentals_by_ticker.items():
        if not f:
            continue
        check = GovernanceCheckInput(
            auditor_opinion="UNQUALIFIED",  # not available from vnstock -- assumed clean, see docstring point 3
            filing_on_time=True,
            warning_status="NONE",
            margin_eligible=True,
            # A missing interest_coverage is NOT the same as a failing one -- verified
            # live, KBS simply doesn't report this ratio for banks (their accounting
            # doesn't have a comparable EBIT/interest-expense figure). Treating "no
            # data" as "0, therefore fails" disqualified every single bank in the
            # universe with the misleading reason "below 3.0x" when the real reason
            # is "not applicable to this sector". Missing -> not evaluated, not failed.
            min_interest_coverage_ok=(f.get("interest_coverage") is None) or (f["interest_coverage"] >= 3.0),
        )
        disq, reasons = governance.is_disqualified(check)
        rows.append({"ticker": ticker, "sector": SECTOR_BY_TICKER.get(ticker, "Other"), "disqualified": disq, "reasons": reasons, **f})

    df = pd.DataFrame(rows)
    if df.empty:
        return df, []

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
    df.loc[~df["disqualified"], "composite_score"] = factors.composite_score(eligible, weights)
    df["percentile_rank"] = df["composite_score"].rank(pct=True) * 100
    df["vif_dropped_factors"] = [dropped] * len(df)
    return df.sort_values("composite_score", ascending=False, na_position="last"), dropped


def build_picks(
    scored: pd.DataFrame,
    in_sample: pd.DataFrame,
    out_sample: pd.DataFrame,
    top_n: int = TOP_N_PICKS,
) -> tuple[list[dict], dict, list[str]]:
    scoreable = scored[scored["composite_score"].notna()]
    top = scoreable.head(top_n).copy()
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

    # Evaluated OUT of sample -- see docstring point 4. Computed on the full
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
                    f"among {len(scoreable)} scoreable tickers. In-sample rank-IC vs trailing "
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


def build_flow_signals(ohlcv_by_ticker: dict[str, pd.DataFrame]) -> dict[str, order_flow.FlowSignal]:
    """One signal per ticker with enough history -- ALL of them, not just anomalies.
    Used both for the rankings table (every row gets a volume column) and,
    filtered to `is_anomalous`, for the "Unusual Buying Activity" panel.
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
        # live: VNM's close came back as ~62-64, i.e. a real price of ~62,000-64,000
        # VND) -- converted to whole VND here so it's not silently 1000x off
        # wherever this feeds portfolio math or gets shown as a currency value.
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
                "last_price": last_price,
                "price_change_pct": sig.price_change_pct if sig else None,
                "relative_volume": sig.relative_volume if sig else None,
                "volume_zscore": sig.volume_zscore if sig else None,
                "flow_direction": sig.direction if sig else None,
            }
        )
    return rows


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
    tickers = [u["ticker"] for u in UNIVERSE]
    log.info("Fetching live data for %d curated tickers...", len(tickers))
    ohlcv_by_ticker, fundamentals_by_ticker = fetch_universe_data(tickers)
    returns_df = build_returns_frame(ohlcv_by_ticker)
    in_sample, out_sample = split_in_out_sample(returns_df)
    log.info("Returns frame: %d trading days (%d in-sample, %d out-of-sample)", len(returns_df), len(in_sample), len(out_sample))

    scored, vif_dropped = screen(fundamentals_by_ticker)
    picks, backtest_summary, pick_tickers = (
        build_picks(scored, in_sample, out_sample) if not scored.empty else ([], {}, [])
    )
    flow_signals = build_flow_signals(ohlcv_by_ticker)
    flow_alerts = build_flow_alerts(flow_signals)
    rankings = build_rankings(scored, flow_signals, ohlcv_by_ticker) if not scored.empty else []

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
            indexed.loc[pick_tickers, factor_cols],
            forward_return_proxy,
        )

    performance = build_performance_series(out_sample, pick_tickers, weights, final_factor_exposures, final_diagnostics)

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
                    "in_sample_days": len(in_sample),
                    "out_of_sample_days": len(out_sample),
                    "note": (
                        "~60 hand-picked liquid HOSE large/mid caps across sectors, not the "
                        "full ~723-ticker universe (vnstock's free-tier rate limit makes "
                        "covering the full market impractical for an hourly refresh). "
                        "Financials are included but scored from whichever factors apply to "
                        "their accounting (see factors_used_count per row) -- ROIC/EV-EBITDA/"
                        "CFO-based ratios don't fit bank accounting. Governance fields are "
                        "assumed clean, not verified against real HOSE disclosures. The "
                        "top-N backtest is evaluated out-of-sample."
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
