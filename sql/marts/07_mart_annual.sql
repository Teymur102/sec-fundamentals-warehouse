-- mart_annual: one wide row per (company, fiscal year), built only from fact_financials.
-- Income-statement and cash-flow items come from the one-year duration; balance-sheet items
-- from the instant on the fiscal-year-end date. Derived fields say where they came from.
create or replace table mart_annual as
with fy_candidates as (
    select p.cik, p.fiscal_year, p.period_key, p.period_start, p.period_end,
           count(f.concept_code) as n_facts
    from dim_period p
    left join fact_financials f using (period_key)
    where p.period_length = 'FY'
    group by all
),
fy as (   -- if a company has two one-year periods for the same fiscal year, keep the fuller one
    select * exclude (rn) from (
        select *, row_number() over (partition by cik, fiscal_year order by n_facts desc, period_end desc) rn
        from fy_candidates
    ) where rn = 1
),
dur as (
    select fy.cik, fy.fiscal_year, f.concept_code, f.value
    from fy join fact_financials f using (period_key)
),
inst as (
    select fy.cik, fy.fiscal_year, f.concept_code, f.value
    from fy
    join dim_period p  on p.cik = fy.cik and p.period_type = 'instant' and p.period_end = fy.period_end
    join fact_financials f on f.period_key = p.period_key
),
wide as (
    select
        fy.cik, fy.fiscal_year, fy.period_start, fy.period_end,
        max(case when x.concept_code = 'revenue'              then x.value end) as revenue_reported,
        max(case when x.concept_code = 'cost_of_revenue'      then x.value end) as cost_of_revenue,
        max(case when x.concept_code = 'gross_profit'         then x.value end) as gross_profit_reported,
        max(case when x.concept_code = 'rd_expense'           then x.value end) as rd_expense,
        max(case when x.concept_code = 'operating_income'     then x.value end) as operating_income,
        max(case when x.concept_code = 'interest_expense'     then x.value end) as interest_expense,
        max(case when x.concept_code = 'pretax_income'        then x.value end) as pretax_income,
        max(case when x.concept_code = 'net_income'           then x.value end) as net_income,
        max(case when x.concept_code = 'net_interest_income'  then x.value end) as net_interest_income,
        max(case when x.concept_code = 'noninterest_income'   then x.value end) as noninterest_income,
        max(case when x.concept_code = 'noninterest_expense'  then x.value end) as noninterest_expense,
        max(case when x.concept_code = 'operating_cash_flow'  then x.value end) as operating_cash_flow,
        max(case when x.concept_code = 'capex'                then x.value end) as capex,
        max(case when x.concept_code = 'total_assets'         then x.value end) as total_assets,
        max(case when x.concept_code = 'total_liabilities'    then x.value end) as total_liabilities_reported,
        max(case when x.concept_code = 'liabilities_and_equity' then x.value end) as liabilities_and_equity,
        max(case when x.concept_code = 'equity_parent'        then x.value end) as equity_parent,
        max(case when x.concept_code = 'equity_total'         then x.value end) as equity_total_reported,
        max(case when x.concept_code = 'noncontrolling_interest' then x.value end) as noncontrolling_interest,
        max(case when x.concept_code = 'temporary_equity'     then x.value end) as temporary_equity,
        max(case when x.concept_code = 'cash'                 then x.value end) as cash,
        max(case when x.concept_code = 'debt_total'           then x.value end) as debt_total_reported,
        max(case when x.concept_code = 'debt_noncurrent'      then x.value end) as debt_noncurrent,
        max(case when x.concept_code = 'debt_current'         then x.value end) as debt_current,
        max(case when x.concept_code = 'deposits'             then x.value end) as deposits
    from fy
    left join (select * from dur union all select * from inst) x
           on x.cik = fy.cik and x.fiscal_year = fy.fiscal_year
    group by all
)
select
    w.*,
    d.ticker, d.sector, d.company_type,
    -- Banks: "revenue" = net interest income + noninterest income (the industry definition).
    -- ASC 606 revenue tags exclude interest, so the reported tag understates bank revenue.
    case when d.company_type = 'bank' and w.net_interest_income is not null and w.noninterest_income is not null
         then w.net_interest_income + w.noninterest_income
         else w.revenue_reported end                                           as revenue,
    case when d.company_type = 'bank' and w.net_interest_income is not null and w.noninterest_income is not null
         then 'derived: NII + noninterest income' else 'reported' end         as revenue_source,
    coalesce(w.gross_profit_reported, w.revenue_reported - w.cost_of_revenue) as gross_profit,
    case when w.gross_profit_reported is not null then 'reported'
         when w.cost_of_revenue is not null       then 'derived: revenue - cost of revenue' end as gross_profit_source,
    coalesce(w.equity_total_reported, w.equity_parent + coalesce(w.noncontrolling_interest, 0)) as equity_total,
    -- ROE uses parent equity (matches parent net income); a few filers (e.g. Biogen) only tag the
    -- total-including-NCI line, so fall back to it.
    coalesce(w.equity_parent, w.equity_total_reported)                       as equity_for_roe,
    coalesce(
        w.total_liabilities_reported,
        w.liabilities_and_equity
          - coalesce(w.equity_total_reported, w.equity_parent + coalesce(w.noncontrolling_interest, 0))
          - coalesce(w.temporary_equity, 0)
    )                                                                         as total_liabilities,
    case when w.total_liabilities_reported is not null then 'reported'
         when w.liabilities_and_equity is not null then 'derived: (L+E) - equity - mezzanine' end as liabilities_source,
    coalesce(w.debt_total_reported, w.debt_noncurrent + coalesce(w.debt_current, 0))  as debt,
    case when w.debt_total_reported is not null then 'reported total'
         when w.debt_noncurrent is not null then 'derived: non-current + current' end as debt_source
from wide w
join dim_company d on d.cik = w.cik;
