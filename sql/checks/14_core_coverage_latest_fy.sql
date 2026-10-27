-- name: Core line items present in latest fiscal year
-- severity: warn
-- description: Lists core line items missing for each company's latest fiscal year (core set depends on company type). Full matrix: output/tables/coverage_latest_fy.csv.
with latest as (
    select * from mart_annual m
    where fiscal_year = (select max(fiscal_year) from mart_annual x where x.cik = m.cik)
),
items as (
    select ticker, company_type, fiscal_year, 'revenue' item, revenue is not null present from latest
    union all select ticker, company_type, fiscal_year, 'net_income', net_income is not null from latest
    union all select ticker, company_type, fiscal_year, 'total_assets', total_assets is not null from latest
    union all select ticker, company_type, fiscal_year, 'shareholders_equity', equity_for_roe is not null from latest
    union all select ticker, company_type, fiscal_year, 'operating_cash_flow', operating_cash_flow is not null from latest
    union all select ticker, company_type, fiscal_year, 'operating_income', operating_income is not null from latest where company_type not in ('bank', 'insurer')
    union all select ticker, company_type, fiscal_year, 'gross_profit', gross_profit is not null from latest where company_type = 'operating'
    union all select ticker, company_type, fiscal_year, 'capex', capex is not null from latest where company_type not in ('bank', 'insurer')
    union all select ticker, company_type, fiscal_year, 'net_interest_income', net_interest_income is not null from latest where company_type = 'bank'
)
select ticker, company_type, fiscal_year, item as missing_item
from items where not present
order by ticker, item;
