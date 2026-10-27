-- sector_medians: median of each ratio across companies in the sector, latest fiscal year.
-- Medians, not means: with 2-7 companies per sector one outlier (e.g. a loss year) would swamp a mean.
create or replace table sector_medians as
with latest as (
    select r.* from ratios_annual r
    where fiscal_year = (select max(fiscal_year) from ratios_annual x where x.cik = r.cik and x.revenue is not null)
)
select
    sector,
    count(*)                       as companies,
    median(revenue_growth)         as revenue_growth,
    median(gross_margin)           as gross_margin,
    median(operating_margin)       as operating_margin,
    median(net_margin)             as net_margin,
    median(roe)                    as roe,
    median(roa)                    as roa,
    median(fcf_margin)             as fcf_margin,
    median(cash_conversion)        as cash_conversion,
    median(debt_to_equity)         as debt_to_equity
from latest
group by sector
order by sector;
