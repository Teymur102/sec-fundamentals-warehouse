-- name: Revenue tag variants disagree
-- severity: warn
-- description: Same company-year reports both Revenues and an ASC 606 revenue tag that differ by more than 1% (tag priority decides which one is used).
with r as (
    select l.cik, l.period_end, l.period_start,
           max(case when tag = 'Revenues' then val end) as revenues_tag,
           max(case when tag = 'RevenueFromContractWithCustomerExcludingAssessedTax' then val end) as asc606_tag
    from int_facts_latest l
    where concept_code = 'revenue' and duration_days between 350 and 380
    group by all
)
select d.ticker, d.company_type, r.period_end, r.revenues_tag, r.asc606_tag,
       round((r.revenues_tag - r.asc606_tag) / r.revenues_tag, 4) as rel_diff
from r join dim_company d on d.cik = r.cik
where r.revenues_tag is not null and r.asc606_tag is not null
  and abs(r.revenues_tag - r.asc606_tag) > 0.01 * abs(r.revenues_tag)
order by d.ticker, r.period_end;
