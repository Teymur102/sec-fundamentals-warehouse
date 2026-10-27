-- name: One fiscal-year period per company-year
-- severity: error
-- description: Each (company, fiscal_year) maps to a single fiscal-year end date (catches fiscal-calendar bugs).
select d.ticker, e.fiscal_year, count(*) as n_fy_ends, string_agg(e.fy_end::varchar, ', ' order by e.fy_end) as fy_ends
from int_fy_ends e join dim_company d on d.cik = e.cik
group by all
having count(*) > 1
order by all;  -- deterministic row order for output/dq_violations
