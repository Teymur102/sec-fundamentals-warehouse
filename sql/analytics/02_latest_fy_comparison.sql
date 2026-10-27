-- latest_fy_comparison: each company's most recent complete fiscal year, ranked within the
-- non-financial group (financials are listed separately in financials_scorecard).
create or replace table latest_fy_comparison as
with latest as (
    select r.* from ratios_annual r
    where fiscal_year = (select max(fiscal_year) from ratios_annual x where x.cik = r.cik and x.revenue is not null)
),
cagr as (
    select l.cik,
           power(l.revenue / r5.revenue, 1.0 / 5) - 1 as revenue_cagr_5y
    from latest l
    join ratios_annual r5 on r5.cik = l.cik and r5.fiscal_year = l.fiscal_year - 5
    where r5.revenue > 0 and l.revenue > 0
)
select
    l.ticker, l.sector, l.company_type, l.fiscal_year, l.period_end,
    l.revenue, l.revenue_growth, c.revenue_cagr_5y,
    l.gross_margin, l.operating_margin, l.net_margin,
    l.roe, l.asset_turnover, l.equity_multiplier,
    l.debt_to_equity, l.fcf_margin, l.cash_conversion, l.rd_intensity,
    -- a NULL metric gets a NULL rank, not "last place"
    case when l.roe is not null then
        rank() over (partition by l.roe is null order by l.roe desc) end                           as rank_roe,
    case when l.operating_margin is not null then
        rank() over (partition by l.operating_margin is null order by l.operating_margin desc) end as rank_operating_margin,
    case when l.revenue_growth is not null then
        rank() over (partition by l.revenue_growth is null order by l.revenue_growth desc) end     as rank_revenue_growth,
    case when l.fcf_margin is not null then
        rank() over (partition by l.fcf_margin is null order by l.fcf_margin desc) end             as rank_fcf_margin
from latest l
left join cagr c on c.cik = l.cik
where not l.is_financial
order by rank_roe nulls last, ticker;
