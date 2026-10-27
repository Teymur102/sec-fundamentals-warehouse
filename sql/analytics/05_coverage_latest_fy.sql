-- coverage_latest_fy: which standard line items each company reports in its latest fiscal year
-- (1 = reported or derivable, 0 = missing).
create or replace table coverage_latest_fy as
select
    ticker, company_type, fiscal_year,
    (revenue is not null)::int              as revenue,
    (gross_profit is not null)::int         as gross_profit,
    (operating_income is not null)::int     as operating_income,
    (net_income is not null)::int           as net_income,
    (rd_expense is not null)::int           as rd_expense,
    (operating_cash_flow is not null)::int  as operating_cash_flow,
    (capex is not null)::int                as capex,
    (total_assets is not null)::int         as total_assets,
    (total_liabilities_reported is not null)::int as total_liabilities_reported,
    (equity_for_roe is not null)::int       as shareholders_equity,
    (debt is not null)::int                 as debt,
    (cash is not null)::int                 as cash,
    (interest_expense is not null)::int     as interest_expense
from mart_annual m
where fiscal_year = (select max(fiscal_year) from mart_annual x where x.cik = m.cik)
order by ticker;
