-- name: Fiscal-year label matches the filing's own fy
-- severity: warn
-- description: For each 10-K, the warehouse's fiscal_year for the filing's own period equals the fy the filer tagged (DocumentFiscalYearFocus).
-- population: select count(*) from int_primary_10k
select d.ticker, k.accn, k.doc_period_end, k.filing_fy, e.fiscal_year as warehouse_fiscal_year
from int_primary_10k k
join int_fy_ends e on e.cik = k.cik and e.fy_end = k.doc_period_end
join dim_company d on d.cik = k.cik
where e.fiscal_year <> k.filing_fy
order by d.ticker, k.doc_period_end;
