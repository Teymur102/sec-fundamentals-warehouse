-- name: Assets = Liabilities-and-equity total
-- severity: error
-- description: Reported Assets equals reported LiabilitiesAndStockholdersEquity (within 0.1%) at every balance-sheet date.
-- population: select count(*) from (select f.company_key, p.period_end from fact_financials f join dim_period p using (period_key) where p.period_type = 'instant' and concept_code in ('total_assets', 'liabilities_and_equity') group by all having count(distinct concept_code) = 2)
with bs as (
    select f.company_key, p.period_end,
           max(case when concept_code = 'total_assets'           then value end) as assets,
           max(case when concept_code = 'liabilities_and_equity' then value end) as l_and_e
    from fact_financials f join dim_period p using (period_key)
    where p.period_type = 'instant'
    group by all
)
select d.ticker, bs.period_end, bs.assets, bs.l_and_e, (bs.assets - bs.l_and_e) / bs.assets as rel_diff
from bs join dim_company d on d.company_key = bs.company_key
where bs.assets is not null and bs.l_and_e is not null
  and abs(bs.assets - bs.l_and_e) > 0.001 * abs(bs.assets);
