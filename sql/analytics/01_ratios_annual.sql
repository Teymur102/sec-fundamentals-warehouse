-- ratios_annual: one row per company-year with every ratio the report uses.
--
-- Banks and insurers ("financials") get a different treatment:
--   * Revenue for banks = net interest income + noninterest income (set in mart_annual).
--   * Gross margin, operating margin, FCF, cash conversion, debt/equity and asset turnover are NULL
--     for financials: their "debt" is raw material (deposits, policy reserves), operating cash flow
--     swings with trading and lending balances, and there is no cost of goods sold.
--   * Financials keep ROE, ROA, equity/assets, and (banks) efficiency ratio and NII share.
-- Averages: ROE/ROA/turnover use the average of opening and closing balances when the prior
-- year exists, otherwise the closing balance. ROE is NULL when average equity <= 0.
create or replace table ratios_annual as
with base as (
    select
        m.*,
        company_type in ('bank', 'insurer')                                   as is_financial,
        lag(fiscal_year)    over w as prior_fy,
        lag(revenue)        over w as prior_revenue,
        lag(total_assets)   over w as prior_assets,
        lag(equity_for_roe) over w as prior_equity
    from mart_annual m
    window w as (partition by cik order by fiscal_year)
),
avgs as (
    select *,
        case when prior_fy = fiscal_year - 1 and prior_assets is not null
             then (total_assets + prior_assets) / 2 else total_assets end    as avg_assets,
        case when prior_fy = fiscal_year - 1 and prior_equity is not null
             then (equity_for_roe + prior_equity) / 2 else equity_for_roe end as avg_equity
    from base
)
select
    cik, ticker, sector, company_type, is_financial, fiscal_year, period_end,
    revenue, net_income, operating_income, total_assets, equity_for_roe as shareholders_equity,
    -- growth
    case when prior_fy = fiscal_year - 1 and prior_revenue > 0
         then revenue / prior_revenue - 1 end                                       as revenue_growth,
    -- margins
    case when company_type = 'operating' then gross_profit / revenue end            as gross_margin,
    case when not is_financial then operating_income / revenue end                  as operating_margin,
    net_income / revenue                                                            as net_margin,
    case when not is_financial then rd_expense / revenue end                        as rd_intensity,
    -- returns + DuPont (3-step for non-financials: margin x turnover x leverage)
    case when avg_equity > 0 then net_income / avg_equity end                       as roe,
    net_income / avg_assets                                                         as roa,
    case when not is_financial then revenue / avg_assets end                        as asset_turnover,
    case when avg_equity > 0 then avg_assets / avg_equity end                       as equity_multiplier,
    -- leverage
    case when not is_financial and equity_for_roe > 0 then debt / equity_for_roe end as debt_to_equity,
    case when equity_total > 0 then total_liabilities / equity_total end            as liabilities_to_equity,
    case when not is_financial and interest_expense > 0
         then operating_income / interest_expense end                               as interest_coverage,
    equity_for_roe / total_assets                                                   as equity_to_assets,
    -- cash flow
    case when not is_financial then operating_cash_flow - capex end                 as free_cash_flow,
    case when not is_financial then (operating_cash_flow - capex) / revenue end     as fcf_margin,
    case when not is_financial and net_income > 0
         then operating_cash_flow / net_income end                                  as cash_conversion,
    -- bank-only
    case when company_type = 'bank' then noninterest_expense / revenue end          as efficiency_ratio,
    case when company_type = 'bank' then net_interest_income / revenue end          as nii_share_of_revenue,
    case when company_type = 'bank' then deposits / total_assets end                as deposits_to_assets,
    revenue_source, gross_profit_source, liabilities_source, debt_source
from avgs;
