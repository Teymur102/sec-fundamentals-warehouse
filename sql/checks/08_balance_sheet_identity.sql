-- name: Balance-sheet identity A = L + E
-- severity: error
-- description: Assets = Liabilities + total equity (incl. noncontrolling interests) + mezzanine equity, within 0.5%, at every balance-sheet date where Liabilities is reported.
-- population: select count(*) from (select f.company_key, p.period_end from fact_financials f join dim_period p using (period_key) where p.period_type = 'instant' group by all having count(case when concept_code = 'total_assets' then 1 end) > 0 and count(case when concept_code = 'total_liabilities' then 1 end) > 0 and count(case when concept_code in ('equity_total', 'equity_parent') then 1 end) > 0)
with bs as (
    select f.company_key, p.period_end,
           max(case when concept_code = 'total_assets'            then value end) as assets,
           max(case when concept_code = 'total_liabilities'       then value end) as liabilities,
           max(case when concept_code = 'equity_total'            then value end) as equity_total,
           max(case when concept_code = 'equity_parent'           then value end) as equity_parent,
           max(case when concept_code = 'noncontrolling_interest' then value end) as nci,
           max(case when concept_code = 'temporary_equity'        then value end) as temporary_equity
    from fact_financials f join dim_period p using (period_key)
    where p.period_type = 'instant'
    group by all
),
calc as (
    select *,
           coalesce(equity_total, equity_parent + coalesce(nci, 0)) as equity_used,
           liabilities + coalesce(equity_total, equity_parent + coalesce(nci, 0)) + coalesce(temporary_equity, 0) as l_plus_e
    from bs
    where assets is not null and liabilities is not null and coalesce(equity_total, equity_parent) is not null
)
select d.ticker, c.period_end, c.assets, c.liabilities, c.equity_used, c.temporary_equity,
       c.assets - c.l_plus_e as gap, round((c.assets - c.l_plus_e) / c.assets, 4) as rel_diff
from calc c join dim_company d on d.company_key = c.company_key
where abs(c.assets - c.l_plus_e) > 0.005 * abs(c.assets)
order by d.ticker, c.period_end;
