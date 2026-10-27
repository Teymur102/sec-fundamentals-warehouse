-- name: Revenue > 0
-- severity: error
-- description: Annual revenue is strictly positive for every company-year that has revenue.
-- population: select count(*) from mart_annual where revenue is not null
select ticker, fiscal_year, revenue, revenue_source
from mart_annual
where revenue is not null and revenue <= 0
order by all;  -- deterministic row order for output/dq_violations
