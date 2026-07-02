CREATE EXTENSION IF NOT EXISTS vector;

CREATE DATABASE ccks_fund;

\connect ccks_fund

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.fund_nav (
    fund_code text NOT NULL,
    trade_date date NOT NULL,
    nav numeric(12, 4) NOT NULL,
    accumulated_nav numeric(12, 4) NOT NULL,
    PRIMARY KEY (fund_code, trade_date)
);

INSERT INTO public.fund_nav (fund_code, trade_date, nav, accumulated_nav)
VALUES
    ('FUND001', DATE '2026-06-26', 1.0245, 1.2845),
    ('FUND001', DATE '2026-06-27', 1.0312, 1.2912),
    ('FUND002', DATE '2026-06-26', 0.9821, 1.1021),
    ('FUND002', DATE '2026-06-27', 0.9918, 1.1118)
ON CONFLICT (fund_code, trade_date) DO NOTHING;

