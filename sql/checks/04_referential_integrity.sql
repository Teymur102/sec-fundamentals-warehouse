-- name: Referential integrity
-- severity: error
-- description: Every fact row points at an existing company, concept and period.
select 'company' as missing_dim, f.period_key, f.concept_code from fact_financials f
 where not exists (select 1 from dim_company d where d.company_key = f.company_key)
union all
select 'concept', f.period_key, f.concept_code from fact_financials f
 where not exists (select 1 from dim_concept c where c.concept_key = f.concept_key)
union all
select 'period', f.period_key, f.concept_code from fact_financials f
 where not exists (select 1 from dim_period p where p.period_key = f.period_key)
order by all;  -- deterministic row order for output/dq_violations
