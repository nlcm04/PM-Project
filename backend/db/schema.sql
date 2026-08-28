-- HOSE Quant Portfolio & Screening Platform -- PostgreSQL + TimescaleDB DDL
-- Run against a database with the timescaledb extension available.

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- assets
-- ============================================================================
CREATE TABLE assets (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL UNIQUE,
    company_name    VARCHAR(255) NOT NULL,
    exchange        VARCHAR(10) NOT NULL DEFAULT 'HOSE',
    sector          VARCHAR(100),
    listing_date    DATE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    margin_eligible BOOLEAN NOT NULL DEFAULT TRUE,
    warning_status  VARCHAR(20) NOT NULL DEFAULT 'NONE'
                        CHECK (warning_status IN ('NONE', 'WARNING', 'CONTROL', 'SUSPENDED'))
);

CREATE INDEX idx_assets_ticker ON assets (ticker);

-- ============================================================================
-- market_data_daily -- TimescaleDB hypertable, one row per (asset, trading day)
-- ============================================================================
CREATE TABLE market_data_daily (
    asset_id    INTEGER NOT NULL REFERENCES assets (id),
    ts          TIMESTAMPTZ NOT NULL,
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    volume      BIGINT NOT NULL,
    ref_price   DOUBLE PRECISION NOT NULL,
    ceiling     DOUBLE PRECISION NOT NULL,   -- ref_price * 1.07
    floor       DOUBLE PRECISION NOT NULL,   -- ref_price * 0.93
    PRIMARY KEY (asset_id, ts)
);

SELECT create_hypertable('market_data_daily', 'ts', if_not_exists => TRUE);
CREATE INDEX idx_market_data_asset_ts ON market_data_daily (asset_id, ts DESC);

-- ============================================================================
-- fundamentals_quarterly
-- ============================================================================
CREATE TABLE fundamentals_quarterly (
    id                  SERIAL PRIMARY KEY,
    asset_id            INTEGER NOT NULL REFERENCES assets (id),
    period_end          DATE NOT NULL,
    earnings_yield      DOUBLE PRECISION,
    book_to_market      DOUBLE PRECISION,
    ev_to_ebitda        DOUBLE PRECISION,
    roic                DOUBLE PRECISION,
    cfo_to_assets       DOUBLE PRECISION,
    interest_coverage   DOUBLE PRECISION,
    auditor_opinion     VARCHAR(20) NOT NULL DEFAULT 'UNQUALIFIED'
                            CHECK (auditor_opinion IN ('UNQUALIFIED', 'QUALIFIED', 'ADVERSE', 'DISCLAIMER')),
    filing_on_time      BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (asset_id, period_end)
);

CREATE INDEX idx_fundamentals_asset ON fundamentals_quarterly (asset_id, period_end DESC);

-- ============================================================================
-- factor_scores -- daily cross-sectional composite score + Grinold expected return
-- ============================================================================
CREATE TABLE factor_scores (
    id                          SERIAL PRIMARY KEY,
    asset_id                    INTEGER NOT NULL REFERENCES assets (id),
    as_of_date                  DATE NOT NULL,
    composite_score             DOUBLE PRECISION NOT NULL,
    percentile_rank             DOUBLE PRECISION NOT NULL,
    information_coefficient     DOUBLE PRECISION NOT NULL,
    expected_active_return      DOUBLE PRECISION NOT NULL,  -- Grinold: IC * sigma_i * S_i
    UNIQUE (asset_id, as_of_date)
);

CREATE INDEX idx_factor_scores_date ON factor_scores (as_of_date DESC);

-- ============================================================================
-- daily_stock_picks -- the human-in-the-loop approval queue
-- ============================================================================
CREATE TABLE daily_stock_picks (
    id                  SERIAL PRIMARY KEY,
    asset_id            INTEGER NOT NULL REFERENCES assets (id),
    pick_date           DATE NOT NULL,
    rationale           TEXT NOT NULL,
    projected_sharpe    DOUBLE PRECISION NOT NULL,
    suggested_weight    DOUBLE PRECISION NOT NULL,
    backtest_summary    JSONB NOT NULL DEFAULT '{}'::jsonb,
    status              VARCHAR(10) NOT NULL DEFAULT 'PENDING'
                            CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    decided_at          TIMESTAMPTZ,
    decided_by          VARCHAR(100)
);

CREATE INDEX idx_picks_status_date ON daily_stock_picks (status, pick_date DESC);

-- ============================================================================
-- holdings -- only ever created via manual approval of a daily_stock_pick
-- ============================================================================
CREATE TABLE holdings (
    id                      SERIAL PRIMARY KEY,
    asset_id                INTEGER NOT NULL REFERENCES assets (id),
    quantity                INTEGER NOT NULL CHECK (quantity % 100 = 0),   -- round-lot constraint
    avg_cost                DOUBLE PRECISION NOT NULL,
    opened_at               DATE NOT NULL,
    closed_at               DATE,
    peak_price_since_open   DOUBLE PRECISION NOT NULL,
    stop_loss_price         DOUBLE PRECISION,                             -- peak - 2.5*ATR
    status                  VARCHAR(15) NOT NULL DEFAULT 'OPEN'
                                CHECK (status IN ('OPEN', 'SELL_SIGNAL', 'CLOSED')),
    sell_signal_reason      TEXT
);

CREATE INDEX idx_holdings_status ON holdings (status);

-- ============================================================================
-- cash_settlements -- T+2 (securities) / T+1.5 (cash) settlement bucket tracking
-- ============================================================================
CREATE TABLE cash_settlements (
    id                  SERIAL PRIMARY KEY,
    asset_id            INTEGER NOT NULL REFERENCES assets (id),
    side                VARCHAR(4) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity            INTEGER NOT NULL CHECK (quantity % 100 = 0),
    price               DOUBLE PRECISION NOT NULL,
    trade_date          DATE NOT NULL,
    settlement_date     DATE NOT NULL,
    status              VARCHAR(10) NOT NULL DEFAULT 'PENDING'
                            CHECK (status IN ('PENDING', 'SETTLED'))
);

CREATE INDEX idx_settlements_settlement_date ON cash_settlements (settlement_date, status);

-- ============================================================================
-- performance_analytics -- daily portfolio snapshot + diagnostics pipeline output
-- ============================================================================
CREATE TABLE performance_analytics (
    id                  SERIAL PRIMARY KEY,
    snapshot_date       DATE NOT NULL UNIQUE,
    nav                 DOUBLE PRECISION NOT NULL,
    sharpe_ratio        DOUBLE PRECISION NOT NULL,
    max_drawdown        DOUBLE PRECISION NOT NULL,
    factor_exposures    JSONB NOT NULL DEFAULT '{}'::jsonb,
    diagnostics         JSONB NOT NULL DEFAULT '{}'::jsonb   -- ADF / Breusch-Pagan / Breusch-Godfrey / VIF results
);

CREATE INDEX idx_performance_date ON performance_analytics (snapshot_date DESC);

-- ============================================================================
-- institutional_flow_alerts -- volume-anomaly "smart money" tracking signal
-- ============================================================================
CREATE TABLE institutional_flow_alerts (
    id                  SERIAL PRIMARY KEY,
    asset_id            INTEGER NOT NULL REFERENCES assets (id),
    as_of_date          DATE NOT NULL,
    relative_volume     DOUBLE PRECISION NOT NULL,   -- today's volume / trailing rolling average
    volume_zscore       DOUBLE PRECISION NOT NULL,
    price_change_pct    DOUBLE PRECISION NOT NULL,
    direction           VARCHAR(15) NOT NULL DEFAULT 'NEUTRAL'
                            CHECK (direction IN ('ACCUMULATION', 'DISTRIBUTION', 'NEUTRAL')),
    foreign_net_value   DOUBLE PRECISION,            -- NULL when the data source doesn't expose foreign flow
    is_anomalous        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asset_id, as_of_date)
);

CREATE INDEX idx_flow_alerts_date_zscore ON institutional_flow_alerts (as_of_date DESC, volume_zscore DESC);
