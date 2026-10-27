-- name: Capex reported as a positive outflow
-- severity: warn
-- description: PaymentsToAcquire* tags are defined as positive numbers; a negative value means a sign error by the filer.
select ticker, fiscal_year, capex from mart_annual where capex < 0
order by all;  -- deterministic row order for output/dq_violations
