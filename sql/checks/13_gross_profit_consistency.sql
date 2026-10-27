-- name: Gross profit = revenue - cost of revenue
-- severity: warn
-- description: Where all three are reported, reported gross profit matches revenue minus cost of revenue within 1%.
-- population: select count(*) from mart_annual where gross_profit_reported is not null and cost_of_revenue is not null and revenue_reported is not null
select ticker, fiscal_year, revenue_reported, cost_of_revenue, gross_profit_reported,
       round((gross_profit_reported - (revenue_reported - cost_of_revenue)) / revenue_reported, 4) as rel_diff
from mart_annual
where gross_profit_reported is not null and cost_of_revenue is not null and revenue_reported is not null
  and abs(gross_profit_reported - (revenue_reported - cost_of_revenue)) > 0.01 * abs(revenue_reported);
