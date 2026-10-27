-- name: Latest fiscal year is recent
-- severity: warn
-- description: Each company's latest fiscal-year end is within 15 months of the run date (a stale company would distort "latest year" comparisons).
select ticker, max(period_end) as latest_fy_end, current_date as run_date
from mart_annual
group by ticker
having max(period_end) < current_date - interval 15 month;
