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
a real vnstock pull; nothing is fabricated. The underlying snapshot refreshes
**hourly during HOSE trading hours** -- the closest a static site can get to
real-time. On top of that, an already-open tab **auto-refreshes its own data
every 5 minutes** (`frontend/lib/useAutoRefresh.ts`) and again immediately
whenever you switch back to it (via the page visibility API), so you don't
need to manually reload to see the next hourly snapshot once it's published
-- it re-fetches the same JSON in place, without a full page reload, so it
never clobbers whatever you're mid-typing into the portfolio form. Approving
a pick doesn't persist anywhere (no server to persist it to), but your own
**portfolio (cash, holdings, trading fee) is editable directly on the site**
and saved to your browser's localStorage -- see "Personal portfolio tracking"
below.

### The scoring model: 7 factors, sector-neutral

`composite_score` blends 7 cross-sectional factors, equal-weighted after
z-scoring: `earnings_yield`, `book_to_market`, `ev_to_ebitda`, `roic`,
`cfo_to_assets` (value/quality, from fundamentals), `momentum` (12-1 month
price momentum -- one of the best-replicated factors in equity markets,
emerging markets included, paired here with value rather than left out), and
`foreign_flow_5d` (rolling foreign net-buy value -- one of the most-watched
signals in the Vietnamese market specifically). Z-scoring is **sector-neutral**
(`app/quant/factors.py::sector_neutral_composite_score`): a bank's ratios are
compared to other financials, not to real estate or industrials, since
valuation multiples aren't comparable across sectors and pooling them biases
the ranking toward whichever sector happens to be cheap right now. Sectors
with fewer than 4 members fall back to the global z-score, since a 2-name
sector's within-group z-scores are just ±1 and not statistically meaningful.

### Backtest: walk-forward across multiple historical folds

`app/quant/backtest.py::walk_forward_evaluate` re-derives the optimizer's
weights at each of several historical folds using an **expanding window of
only the data before that fold**, evaluates on the fold, and concatenates all
folds into one continuous multi-regime equity curve -- not a single static
70/30 split, which only tells you about one period. Today's live
recommendation still uses ALL available history (most current information);
the walk-forward folds exist purely to test whether the weight-derivation
methodology holds up across different historical stretches. Honest limit:
`score_z` (which stocks are attractive) is held fixed at today's value, not
re-derived at each historical fold -- a fully rigorous walk-forward would
also re-score stocks using point-in-time historical fundamentals (vnstock's
`Finance.ratio()` does return multiple historical quarters, so this is
possible in principle, just not implemented here).

### Foreign flow: a persisted snapshot, not a real historical series

vnstock has no verified historical foreign-flow endpoint -- checked live,
`Trading.history()` isn't actually implemented for either data source despite
appearing in the class's method list. `foreign_flow_5d` is built by taking a
live snapshot each run and **persisting it across runs into
`data/foreign_flow_history.json`, committed back to the repo by CI** (GitHub
Actions runners are ephemeral; the git repo itself is the only persistence
available). The factor starts thin (one data point) and improves day by day
as history accumulates -- `meta.json`'s `foreign_flow_history_days` shows how
much has built up so far.

Other deliberate scope limits of this snapshot, surfaced on the site itself
(and in `frontend/public/data/meta.json`), not hidden:
- **~60-name curated universe, not the full ~723 HOSE tickers.** Two reasons:
  vnstock's free-tier rate limiter was observed live to kill the whole Python
  process (`SystemExit`, not a catchable exception) after roughly 10 tickers
  when called too fast, and pulling the full market every run at a safe pace
  would take well over an hour, defeating an hourly refresh; and pulling ~700
  tickers per run against a free, scraping-based API on every CI run isn't a
  considerate load either way. `build_static_snapshot.py` paces requests at
  3.5s apart and stops early rather than crash if it still gets rate-limited.
  Each run now makes 3 calls per ticker (OHLCV, fundamentals, foreign-flow
  snapshot), so a full run takes ~15-18 minutes.
- **Financials (banks, brokers) are included**, scored from whichever
  factors actually apply to their accounting -- a live pull showed ACB (a
  bank) returning `None` for ROIC/EV-EBITDA/CFO-based ratios, so a bank
  typically scores off just earnings_yield/book_to_market/momentum/foreign_flow
  (disclosed per-row as `factors_used_count`). An earlier version of this
  screen also disqualified every bank outright, treating "no interest
  coverage data" the same as "fails the 3x interest-coverage check" --
  verified live and fixed; missing now means "not evaluated," not "failed."
- **Governance fields are assumed clean**, not verified -- vnstock doesn't
  expose auditor opinion, filing status, or the HOSE warning list (see
  `app/data/vnstock_client.py`), so this list is "hand-picked large/mid
  caps", not "governance-screened".
- Only shortlisted names the optimizer actually allocates a real weight to
  are shown in "Today's Optimizer Shortlist" -- a name weighted at ~0% (this
  happens; verified live) is dropped rather than shown as an actionable
  recommendation with no allocation. It still appears, unstarred, in the full
  rankings table.

**How it's wired up** (`.github/workflows/deploy_frontend.yml`, runs on every
push touching `frontend/**`/`backend/**`, hourly during HOSE trading hours,
and on manual dispatch):
1. Installs backend deps and runs `build_static_snapshot.py`, writing
   `picks.json` (the optimizer's shortlist), `rankings.json` (every fetched
   ticker, scored or not), `holdings.json` (always empty -- no brokerage
   integration; your own portfolio lives in your browser instead), `performance.json`,
   `flow_alerts.json`, and `meta.json` into `frontend/public/data/`.
2. Commits `data/foreign_flow_history.json` back to the repo if it changed
   (see "Foreign flow" above) -- best-effort, `continue-on-error: true`, so a
   rare push conflict doesn't block the site deploy itself.
3. Builds `frontend/` with `next build`, `NEXT_PUBLIC_DATA_MODE=static`
   (routes every `lib/api.ts` call to those JSON files instead of a live API)
   and `NEXT_PUBLIC_BASE_PATH=/PM-Project` (GitHub Pages project sites are
   served under `/<repo-name>/`, not `/`), set in `next.config.mjs`, which
   also sets `output: "export"` for plain static HTML/CSS/JS.
4. Publishes `frontend/out/` via `actions/upload-pages-artifact` +
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

## Personal portfolio tracking

The Portfolio Health page lets you enter your own cash balance, trading fee
(default 0.1% per side), and holdings (ticker, buy price, quantity) --
`frontend/lib/portfolio.ts` / `usePortfolio.ts`. This is deliberately **client-side
only**: it's saved to your browser's `localStorage`, not sent anywhere, because
there is no backend behind the deployed site to send it to. That means it's
private to whichever browser/device you entered it on, and is lost if you
clear site data -- a real trade-off, not a hidden one.

Market value and unrealized P&L (both gross and net of your round-trip fee)
are computed against `rankings.json`'s `last_price` for any held ticker in
the tracked ~60-name universe; a ticker outside that universe falls back to
your buy price with an "n/a" marker rather than pretending to have live data
for it. Each time you visit the page, today's computed NAV is upserted into a
second `localStorage` series (`recordNavHistoryPoint`), building your own
real equity curve over time -- Sharpe and max drawdown on that curve are
computed client-side and only shown once there's enough history (5+ points)
to be more than noise. Until you enter any cash or holdings, the page falls
back to showing the backtested optimizer-shortlist curve instead.

## Daily Discovery: full rankings table

Rather than a shortlist of cards, Daily Discovery shows every fetched ticker
in one sortable table (`components/discovery/RankingsTable.tsx`) -- composite
score, percentile, all 5 factor values, last price, day change, relative
volume, and volume z-score, click any column to sort. Disqualified or
insufficiently-scored rows are included (faded, not hidden) rather than
silently dropped, and a ★ marks names in that day's optimizer shortlist
(shown separately above the table with its rationale and basket-level
backtest stats, since those are portfolio-level numbers a per-row table can't
represent). Sorting a ranking table where null scores should always sort
last, independent of ascending/descending, is easy to get backwards -- an
earlier version of the sort comparator did exactly that (multiplying the
null-handling branch by the direction flag inverted it under descending
sort); verified live and fixed.

## What's real vs. what's a v1 foundation

This was built and verified in one pass, but is honestly a **v1 foundation**,
not a deployed production system. Specifically:

- **Verified working, live**: the `vnstock` data layer (`app/data/vnstock_client.py`)
  was smoke-tested against real HOSE data during development -- fetched real
  OHLCV history for VNM, the full 723-ticker HOSE universe, a live price board
  (ref/ceiling/floor + foreign buy/sell value), and value/quality ratios
  (P/E, P/B, EV/EBITDA, ROCE, interest coverage, CFO/Assets) for VNM, VIC, and
  ACB, and a real ~60-ticker sector-neutral screening + walk-forward backtest
  run for the GitHub Pages snapshot (see below), including a live foreign-flow
  snapshot for all 61 tickers persisted into `data/foreign_flow_history.json`.
  All 64 backend unit tests pass. The FastAPI app imports cleanly and its
  OpenAPI schema generates. The Next.js
  frontend builds cleanly under strict TypeScript and was verified in a
  browser -- theme/fonts/routing, the rankings table's sort correctness, the
  portfolio editor's add/remove/persist-across-reload behavior with no
  hydration-mismatch errors, and graceful empty/error states with no backend
  attached.
- **Found and fixed a real upstream bug**: `Finance.ratio()` on vnstock's
  default `VCI` source returns stale, mislabeled period columns (every quarter
  came back headed "2018" regardless of what was requested) -- verified live,
  not assumed. `get_fundamentals`/`get_raw_ratio_table` now hard-code the `KBS`
  source instead, which returns correct, current-quarter data with stable
  English `item_id` keys. Run `python -m scripts.ingest_fundamentals` to
  populate `fundamentals_quarterly` for registered assets.
- **Found and fixed a units bug**: `Quote.history()`'s `close` price is in
  **thousands** of VND (verified live: VNM's close came back as ~62-64, a
  real price of ~62,000-64,000 VND) -- `rankings.json`'s `last_price` and
  the portfolio's market-value math both convert to whole VND explicitly
  rather than silently being 1000x off wherever a price gets used as money.
- **Found and fixed a drawdown bug**: a per-day "max_drawdown" field
  computed as `nav / running_peak - 1` only ever showed that DAY's
  drawdown-from-peak, not the worst drawdown seen up to that point -- so on
  any day the price had partly recovered, the stat understated real risk.
  Verified live: a walk-forward run's last day showed "-4.5% max drawdown"
  while the actual worst point in the same run was -19.2%. Compounding that,
  the very first period's drawdown was ALWAYS trivially 0 regardless of how
  bad that period's return was, because `cummax()` at the first element is
  just that element -- there's no prior peak yet unless the starting capital
  is explicitly included as a reference point. Both fixed in
  `app/quant/backtest.py::drawdown_series`/`max_drawdown`, used everywhere a
  drawdown number is computed.
- **Found and fixed a VIF crash on an all-missing-factor universe**: an
  all-banks screen (every row missing `ev_to_ebitda`/`roic`/`cfo_to_assets`)
  made `prune_by_vif`'s internal `.dropna()` empty out entirely and crash
  with a `LinAlgError` instead of falling back to scoring with whatever
  factors are actually available. `app/quant/screener.py` now has the same
  minimum-complete-rows guard as the static snapshot script.
- **Not verified end-to-end**: nothing here has run against a live Postgres/
  TimescaleDB instance (no Docker available in the build environment). The
  `db/schema.sql` DDL and SQLAlchemy models were hand-reviewed for correctness
  but not executed. Boot the stack (below) and check for migration errors
  before trusting it blindly.
- **Known data gap**: vnstock does not expose auditor opinion, on-time filing
  status, or HOSE warning/special-control-list membership -- the governance
  fields in `fundamentals_quarterly` need a separate, manually-curated feed
  (e.g. from HOSE's own disclosure portal). `screen_universe()` still fails
  closed on those specific fields (treats them as disqualifying if unset),
  but a missing `interest_coverage` no longer does -- see the interest-
  coverage fix above.
- **`app/quant/screener.py` (the DB-backed path) does NOT yet have the
  momentum, foreign-flow, or walk-forward fixes** that the GitHub Pages
  static snapshot has -- it does have the sector-neutral scoring and
  missing-interest-coverage fixes, since those needed no schema changes.
  Adding momentum/foreign-flow there would need real schema additions (a
  persisted foreign-flow history table, a returns-fetch step) that can't be
  verified without a live database anyway -- documented as an open gap in
  the module's own docstring rather than half-implemented.
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
python -m pytest       # 52 tests, no DB required
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
- **Momentum** (12-1 month, skipping the most recent month to avoid
  short-term reversal) and **foreign-flow** (rolling foreign net-buy,
  persisted across CI runs) as two additional cross-sectional factors,
  paired with value/quality rather than screened separately
  (`app/quant/factors.py::momentum_12_1`, `scripts/build_static_snapshot.py`)
- **Sector-neutral scoring**: factors are z-scored within each sector, not
  pooled across the whole universe (`app/quant/factors.py::sector_neutral_composite_score`)
- **No-scandal governance gate**: instant disqualification, no partial credit
  (`app/quant/governance.py`)
- **Grinold Rule + Fundamental Law of Active Management**: `app/quant/grinold.py`
- **Econometric diagnostics** (ADF, Breusch-Pagan, Breusch-Godfrey, VIF pruning):
  `app/quant/diagnostics.py`, run automatically each screening cycle
- **Long-only, lot-constrained, max-Sharpe optimizer**: `app/quant/optimizer.py`
- **Walk-forward backtest** across multiple historical folds (expanding
  window, folds concatenated into one multi-regime curve), not a single
  static split: `app/quant/backtest.py::walk_forward_evaluate`
- **HOSE microstructure**: 100-share lots, ±7% price bands, T+2/T+1.5
  settlement bucketing (`app/quant/microstructure.py`)
- **Strict, low-churn sell rules** (2-consecutive-quarter percentile
  degradation, governance violation, 2.5×ATR trailing stop -- nothing else):
  `app/quant/sell_rules.py`
