-- financials_scorecard: banks and the insurer, on the ratios that make sense for them.
create or replace table financials_scorecard as
select
    ticker, company_type, fiscal_year, period_end,
    revenue, net_income, total_assets, shareholders_equity,
    roe, roa, equity_multiplier, equity_to_assets,
    efficiency_ratio, nii_share_of_revenue, deposits_to_assets, net_margin
from ratios_annual
where is_financial
  and fiscal_year >= (select max(fiscal_year) - 2 from ratios_annual)
order by ticker, fiscal_year;
