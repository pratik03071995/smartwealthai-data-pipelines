CREATE TABLE IF NOT EXISTS sw_gold.earnings_calendar (
  ticker STRING,
  earnings_date DATE,
  eps_estimate DOUBLE,
  eps_actual DOUBLE,
  surprise_pct DOUBLE,
  fiscal_year INT,
  fiscal_quarter INT,
  company_name STRING,
  sector STRING,
  industry STRING,
  source STRING,
  ingested_at_utc TIMESTAMP
)
USING DELTA;
