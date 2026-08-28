# HOSE Quant Portfolio & Screening Platform

A human-in-the-loop value/quality screening and portfolio-tracking platform for
HOSE (Ho Chi Minh City Stock Exchange) equities. The screening engine never
auto-invests: it only ever writes `PENDING` rows to `daily_stock_picks`; a
stock becomes a tracked holding solely through a manual "Approve" click in the
Daily Discovery UI.

## Live demo on GitHub Pages

**https://nlcm04.github.io/PM-Project/**

This is the frontend only, built as a static export with sample/fixture data
(`frontend/lib/sampleData.ts`) -- there is no live backend or database behind
it. GitHub Pages can only serve static files, so it can't run FastAPI or
Postgres; this demo exists to show the UI (Daily Discovery, Portfolio Health,
institutional flow alerts), not real screening output. A "Demo mode" badge is
shown in the sidebar so it's never confused for live data. Approve/Reject
buttons work against the in-memory sample data (resets on reload).

**How it's wired up** (`.github/workflows/deploy_frontend.yml`, runs on every
push to `main` that touches `frontend/**`):
1. Builds `frontend/` with `next build`, with `NEXT_PUBLIC_DEMO_MODE=true`
   (routes every `lib/api.ts` call to the sample fixtures instead of a real
   API) and `NEXT_PUBLIC_BASE_PATH=/PM-Project` (GitHub Pages project sites
   are served under `/<repo-name>/`, not `/`) set in `next.config.mjs`, which
   also sets `output: "export"` to produce plain static HTML/CSS/JS in
   `frontend/out/` instead of requiring a Node server.
2. Publishes `frontend/out/` via `actions/upload-pages-artifact` +
   `actions/deploy-pages`.

**One-time repo setting this depends on** (already done for this repo, but
needed if you fork it or start fresh): Settings -> Pages -> Build and
deployment -> Source must be **"GitHub Actions"**, not "Deploy from a
branch". If it's on a branch source, the workflow's `deploy-pages` step will
either fail or silently deploy nowhere useful.

To point the demo at a real backend instead of sample data, drop
`NEXT_PUBLIC_DEMO_MODE` from the workflow's `env:` block and set
`NEXT_PUBLIC_API_BASE_URL` there to your hosted FastAPI URL -- see "What's
real vs. what's a v1 foundation" below for what hosting that requires.

## What's real vs. what's a v1 foundation

This was built and verified in one pass, but is honestly a **v1 foundation**,
not a deployed production system. Specifically:

- **Verified working, live**: the `vnstock` data layer (`app/data/vnstock_client.py`)
  was smoke-tested against real HOSE data during development -- fetched real
  OHLCV history for VNM, the full 723-ticker HOSE universe, a live price board
  (ref/ceiling/floor + foreign buy/sell value), and value/quality ratios
  (P/E, P/B, EV/EBITDA, ROCE, interest coverage, CFO/Assets) for VNM, VIC, and
  ACB. All 30 backend unit tests pass. The FastAPI app imports cleanly and its
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
