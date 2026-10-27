-- name: DuPont components multiply back to ROE
-- severity: error
-- description: For non-financials, net margin x asset turnover x equity multiplier equals ROE (to 1e-9). Guards the analytics layer against denominator mismatches.
-- population: select count(*) from ratios_annual where roe is not null and asset_turnover is not null and net_margin is not null
select ticker, fiscal_year, roe, net_margin * asset_turnover * equity_multiplier as product
from ratios_annual
where roe is not null and asset_turnover is not null and net_margin is not null
  and abs(roe - net_margin * asset_turnover * equity_multiplier) > 1e-9;
