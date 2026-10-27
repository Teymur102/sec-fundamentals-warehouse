-- name: Not-null keys and values
-- severity: error
-- description: Fact keys/values, company identifiers and fiscal years on one-year periods are never null.
select 'fact_financials' as tbl, period_key as key_value from fact_financials
 where period_key is null or company_key is null or concept_key is null or value is null or source_tag is null
union all
select 'dim_company', cik::varchar from dim_company where ticker is null or entity_name is null or sector is null or company_type is null
union all
select 'dim_period (FY without fiscal_year)', period_key from dim_period where period_length = 'FY' and fiscal_year is null
order by all;  -- deterministic row order for output/dq_violations
