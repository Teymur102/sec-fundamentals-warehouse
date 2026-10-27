-- name: Primary key: fact_financials
-- severity: error
-- description: Exactly one value per (company, line item, period).
-- population: select count(*) from fact_financials
select company_key, concept_code, period_key, count(*) as n
from fact_financials
group by all
having count(*) > 1
order by all;  -- deterministic row order for output/dq_violations
