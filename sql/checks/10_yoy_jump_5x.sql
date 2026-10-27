-- name: Year-over-year jumps > 5x
-- severity: warn
-- description: Flags annual values that moved more than 5x (up or down) vs the prior fiscal year. Not always wrong - each needs a look.
-- population: select (select count(*) from mart_annual where revenue is not null) + (select count(*) from mart_annual where total_assets is not null) + (select count(*) from mart_annual where equity_parent is not null) + (select count(*) from mart_annual where operating_cash_flow is not null) + (select count(*) from mart_annual where net_income is not null)
with series as (
    select ticker, fiscal_year, 'revenue' as item, revenue as v from mart_annual
    union all select ticker, fiscal_year, 'total_assets', total_assets from mart_annual
    union all select ticker, fiscal_year, 'equity_parent', equity_parent from mart_annual
    union all select ticker, fiscal_year, 'operating_cash_flow', operating_cash_flow from mart_annual
    union all select ticker, fiscal_year, 'net_income', net_income from mart_annual
),
lagged as (
    select *, lag(v) over (partition by ticker, item order by fiscal_year) as prior_v,
              lag(fiscal_year) over (partition by ticker, item order by fiscal_year) as prior_year
    from series where v is not null
)
select ticker, item, fiscal_year, prior_v, v, round(abs(v) / abs(prior_v), 2) as abs_ratio,
       case when sign(v) <> sign(prior_v) then 'sign flip' else 'same sign' end as sign_change
from lagged
where prior_year = fiscal_year - 1 and prior_v <> 0 and v <> 0
  and (abs(v) / abs(prior_v) > 5 or abs(v) / abs(prior_v) < 0.2)
order by item, ticker, fiscal_year;
