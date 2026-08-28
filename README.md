# HOSE Quant Portfolio & Screening Platform

A human-in-the-loop value/quality screening and portfolio-tracking platform for
HOSE (Ho Chi Minh City Stock Exchange) equities. The screening engine never
auto-invests: it only ever writes `PENDING` rows to `daily_stock_picks`; a
stock becomes a tracked holding solely through a manual "Approve" click in the
Daily Discovery UI.

## Live demo on GitHub Pages

**https://nlcm04.github.io/PM-Project/**

GitHub Pages can only serve static files -- it can't run FastAPI or Postgres.
Rather than fake that with sample data, `backend/scripts/build_static_snapshot.py`
runs the **real** screening + backtest pipeline against **live vnstock data**
at CI build time (no database involved) and writes the result as static JSON
that the frontend fetches directly. Every number on the live site came out of
a real vnstock pull; nothing is fabricated. It refreshes daily. It's still
read-only, though -- there is no server behind the deployed site to persist an
Approve/Reject decision to, and the sidebar says so.

Deliberate scope limits of this snapshot, surfaced on the site itself (and in
`frontend/public/data/meta.json`), not hidden:
- **Curated ~20-name universe, not the full ~723 HOSE tickers**, and
  financials/banks are excluded entirely. Two reasons: a live pull showed
  ACB (a bank) returning `None` for ROIC/EV-EBITDA/CFO-based ratios -- those
  metrics don't fit bank accounting, so scoring them would be silently wrong,
  not silently missing; and pulling ~700 tickers per run against a free,
  scraping-based API on every CI run isn't a considerate load. vnstock's rate
  limiter was observed live to kill the whole process (`SystemExit`, not a
  catchable exception) after roughly 10 tickers when called too fast --
  `build_static_snapshot.py` paces requests at 3.5s apart and stops early
  rather than crash if it still gets rate-limited.
- **Governance fields are assumed clean**, not verified -- vnstock doesn't
  expose auditor opinion, filing status, or the HOSE warning list (see
  `app/data/vnstock_client.py`), so this list is "hand-picked blue chips",
  not "governance-screened".
- **Out-of-sample backtest, on purpose**: expected returns, the covariance
  matrix, and portfolio weights are computed on the first ~70% of the lookback
  window; Sharpe, drawdown, the equity curve, and the vs-random-baskets
  comparison are evaluated on the last ~30%, which weight-selection never
  sees. Computing both halves on the same window would inflate the numbers --
  this is why the live demo's Sharpe is a modest ~0.14, not a suspiciously
  great backtest.
- Only names the optimizer actually allocates a real weight to are shown as
  "picks" -- a shortlisted name that the optimizer weighted at ~0% (this
  happens; verified live) is dropped rather than shown as an actionable
  recommendation with no allocation.

**How it's wired up** (`.github/workflows/deploy_frontend.yml`, runs on every
push touching `frontend/**`/`backend/**`, on a daily schedule, and on manual
dispatch):
1. Installs backend deps and runs `build_static_snapshot.py`, writing
   `picks.json`, `holdings.json` (always empty -- no brokerage integration),
   `performance.json`, `flow_alerts.json`, and `meta.json` into
   `frontend/public/data/`.
2. Builds `frontend/` with `next build`, `NEXT_PUBLIC_DATA_MODE=static`
   (routes every `lib/api.ts` call to those JSON files instead of a live API)
   and `NEXT_PUBLIC_BASE_PATH=/PM-Project` (GitHub Pages project sites are
   served under `/<repo-name>/`, not `/`), set in `next.config.mjs`, which
   also sets `output: "export"` for plain static HTML/CSS/JS.
3. Publishes `frontend/out/` via `actions/upload-pages-artifact` +
   `actions/deploy-pages`.

There's also a third mode, `NEXT_PUBLIC_DATA_MODE=demo`, using
`frontend/lib/sampleData.ts` -- pure fixture data with no vnstock calls at
all, useful for UI development without waiting on a live data pull. The
default (unset) mode is `api`, which talks to a real FastAPI backend.

**One-time repo setting this depends on** (already done for this repo, but
needed if you fork it or start fresh): Settings -> Pages -> Build and
deployment -> Source must be **"GitHub Actions"**, not "Deploy from a
branch". If it's on a branch source, the workflow's `deploy-pages` step will
either fail or silently deploy nowhere useful.

To point the site at a real backend instead (making Approve/Reject actually
persist), set `NEXT_PUBLIC_DATA_MODE=api` and `NEXT_PUBLIC_API_BASE_URL` to
your hosted FastAPI URL in the workflow's `env:` block -- see "What's real
vs. what's a v1 foundation" below for what hosting that requires.

## What's real vs. what's a v1 foundation

This was built and verified in one pass, but is honestly a **v1 foundation**,
not a deployed production system. Specifically:

- **Verified working, live**: the `vnstock` data layer (`app/data/vnstock_client.py`)
  was smoke-tested against real HOSE data during development -- fetched real
  OHLCV history for VNM, the full 723-ticker HOSE universe, a live price board
  (ref/ceiling/floor + foreign buy/sell value), and value/quality ratios
  (P/E, P/B, EV/EBITDA, ROCE, interest coverage, CFO/Assets) for VNM, VIC, and
  ACB, and a real screening + out-of-sample backtest run for the GitHub Pages
  snapshot (see below). All 33 backend unit tests pass. The FastAPI app
  imports cleanly and its
  OpenAPI schema generates. The Next.js frontend builds cleanly under strict
  TypeScript and was verified in a browser (correct theme, fonts, routing, and
  graceful empty/error states with no backend attached).
- **Found and fixed a real upstream bug**: `Finance.ratio()` on vnstock's
  default `VCI` source returns stale, mislabeled period columns (every quarter
  came back headed "2018" regardless of what was requested) -- verified live,
  not assumed. `get_fundamentals`/`get_raw_ratio_table` now hard-code the `KBS`
  source instead, which returns correct, current-quarter data with stable
  English `item_id` keys. Run `python -m scripts.ingest_fundamentals` to
  populate `fundamentals_quarterly` for registered assets.
- **Not verified end-to-end**: nothing here has run against a live Postgres/
  TimescaleDB instance (no Docker available in the build environment). The
  `db/schema.sql` DDL and SQLAlchemy models were hand-reviewed for correctness
  but not executed. Boot the stack (below) and check for migration errors
  before trusting it blindly.
- **Known data gap**: vnstock does not expose auditor opinion, on-time filing
  status, or HOSE warning/special-control-list membership -- the governance
  fields in `fundamentals_quarterly` need a separate, manually-curated feed
  (e.g. from HOSE's own disclosure portal). `screen_universe()` fails closed
  (treats unset governance fields as disqualifying) rather than assuming a
  stock is clean.
- **Data-quality caveat, unresolved**: `cfo_to_assets` came back as exactly
  `0.0` for the latest quarter for both VNM and VIC, while an earlier quarter
  for the same metric was a real non-zero number -- likely "not yet reported
  for this interim period" rather than a true zero, but that's inferred, not
  confirmed against vnstock's own documentation. A 0.0 here could wrongly
  fail the spec's `CFO/Assets > 0` governance check for a healthy company;
  worth a manual sanity check before trusting it in production.
- **Backtest honesty**: the spec asks the backtest to prove "no alternative
  subset out-risk-adjusts the picks." A true proof requires exhaustively
  searching every subset of the HOSE universe, which is combinatorially
  infeasible. `app/quant/backtest.py::compare_against_alternatives` instead
  benchmarks against hundreds of random same-size baskets and reports a
  percentile rank -- a documented heuristic, not a proof.
- **GitHub Actions cron**: the workflow is wired up but will fail on GitHub's
  runners until you add a `DATABASE_URL` secret pointing to a *reachable,
  hosted* Postgres/TimescaleDB instance (e.g. Timescale Cloud's free tier). A
  local `docker-compose` database is not reachable from Actions.

## Repository layout

```
backend/    FastAPI app, quant engine, vnstock ingestion, DDL + Alembic scaffold
frontend/   Next.js 14 (App Router) dashboard: Daily Discovery + Portfolio Health
docker-compose.yml   Local Postgres + TimescaleDB for development
.github/workflows/daily_pipeline.yml   Daily cron (screening + flow-alert scan)
```

## Local setup

### 1. Database
```bash
docker compose up -d
```
This boots Postgres+TimescaleDB and applies `backend/db/schema.sql` on first
init. If you don't have Docker installed, install Docker Desktop first --
that's the only missing piece; everything else in this repo was built and
tested without it.

### 2. Backend
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # or .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env   # adjust DATABASE_URL if not using the default docker-compose creds
python -m pytest       # 26 tests, no DB required
uvicorn app.main:app --reload
```
Then, once the DB is up and `assets` has rows (see below):
```bash
python -m scripts.ingest_market_data     # pulls OHLCV via vnstock
python -m scripts.ingest_fundamentals    # pulls value/quality ratios via vnstock
python -m scripts.detect_flow_alerts     # institutional order-flow scan
python -m scripts.run_daily_pipeline     # writes today's PENDING picks
```
`assets` starts empty -- `ingest_market_data.py` only ingests tickers already
registered there. Seed it with the tickers you want to track (ticker, company
name, sector) before running the pipeline, or extend the script to
auto-register every `vnstock_client.get_hose_universe()` ticker if you want
full-universe coverage from day one.

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```
Visit `http://localhost:3000` -- redirects to `/discovery`.

## Institutional order-flow ("smart money") tracking

`app/quant/order_flow.py` flags a stock when today's volume is a statistical
outlier (z-score-based) relative to its own trailing history, tagged
ACCUMULATION or DISTRIBUTION by the same day's price move -- a proxy for
informed institutional buying/selling. `scripts/detect_flow_alerts.py` scans
every asset with recent price history (not just today's picks) and writes
anomalies to `institutional_flow_alerts`; the Daily Discovery page surfaces
them both as a standalone "Unusual Buying Activity" panel and as an inline
badge on any pick that coincides with one. This only ever reads public
OHLCV/foreign-flow data via vnstock -- there is no non-public order-book access.

## Strategy rules implemented (see the attached spec PDF for full detail)

- **Cheapness/quality filters**: E/P, B/M, EV/EBITDA, ROIC, CFO/Assets,
  interest coverage (`app/quant/factors.py`)
- **No-scandal governance gate**: instant disqualification, no partial credit
  (`app/quant/governance.py`)
- **Grinold Rule + Fundamental Law of Active Management**: `app/quant/grinold.py`
- **Econometric diagnostics** (ADF, Breusch-Pagan, Breusch-Godfrey, VIF pruning):
  `app/quant/diagnostics.py`, run automatically each screening cycle
- **Long-only, lot-constrained, max-Sharpe optimizer**: `app/quant/optimizer.py`
- **HOSE microstructure**: 100-share lots, ±7% price bands, T+2/T+1.5
  settlement bucketing (`app/quant/microstructure.py`)
- **Strict, low-churn sell rules** (2-consecutive-quarter percentile
  degradation, governance violation, 2.5×ATR trailing stop -- nothing else):
  `app/quant/sell_rules.py`
