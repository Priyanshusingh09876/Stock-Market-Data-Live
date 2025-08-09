-- Market Data Pipeline Database Initialization

-- Enable TimescaleDB extension (if available)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create tables for market data
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL'))
);

CREATE TABLE IF NOT EXISTS quotes (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL,
    bid_price DOUBLE PRECISION NOT NULL,
    ask_price DOUBLE PRECISION NOT NULL,
    bid_size BIGINT NOT NULL,
    ask_size BIGINT NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_symbol_time ON quotes(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(time DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_time ON quotes(time DESC);

-- Create hypertables if TimescaleDB is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('trades', 'time', if_not_exists => TRUE);
        PERFORM create_hypertable('quotes', 'time', if_not_exists => TRUE);
    END IF;
END$$;

-- Insert some sample data for testing
INSERT INTO trades (symbol, price, volume, side) VALUES
    ('AAPL', 175.50, 100, 'BUY'),
    ('GOOGL', 140.25, 200, 'SELL'),
    ('MSFT', 380.00, 150, 'BUY')
ON CONFLICT DO NOTHING;

INSERT INTO quotes (symbol, bid_price, ask_price, bid_size, ask_size) VALUES
    ('AAPL', 175.45, 175.55, 500, 600),
    ('GOOGL', 140.20, 140.30, 300, 400),
    ('MSFT', 379.95, 380.05, 200, 250)
ON CONFLICT DO NOTHING;

-- Create a view for latest prices
CREATE OR REPLACE VIEW latest_prices AS
SELECT DISTINCT ON (symbol)
    symbol,
    price as last_price,
    volume as last_volume,
    side as last_side,
    time as last_trade_time
FROM trades
ORDER BY symbol, time DESC;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
