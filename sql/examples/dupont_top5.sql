-- Where does return on equity come from? DuPont split for the five highest-ROE
-- non-financial companies in their latest fiscal year.
select
    ticker,
    fiscal_year,
    round(roe, 3)               as roe,
    round(net_margin, 3)        as net_margin,
    round(asset_turnover, 2)    as asset_turnover,
    round(equity_multiplier, 2) as equity_multiplier
from ratios_annual r
where not is_financial
  and roe is not null
  and fiscal_year = (select max(fiscal_year) from ratios_annual x where x.cik = r.cik)
order by roe desc, ticker
limit 5;
