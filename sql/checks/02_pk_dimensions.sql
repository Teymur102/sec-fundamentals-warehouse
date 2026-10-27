-- name: Primary keys: dimensions
-- severity: error
-- description: dim_company.company_key, dim_concept.concept_code, dim_period.period_key and map_xbrl_tag.tag are unique.
select 'dim_company' as tbl, company_key::varchar as key_value, count(*) as n from dim_company group by all having count(*) > 1
union all
select 'dim_concept', concept_code, count(*) from dim_concept group by all having count(*) > 1
union all
select 'dim_period', period_key, count(*) from dim_period group by all having count(*) > 1
union all
select 'map_xbrl_tag (a tag may feed only one line item)', tag, count(*) from map_xbrl_tag group by all having count(*) > 1
order by all;  -- deterministic row order for output/dq_violations
