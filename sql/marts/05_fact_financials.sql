-- fact_financials: one value per (company, standard line item, period).
--
-- Dedupe step 2: several tags can map to the same line item for the same period
-- (e.g. a company reports both Revenues and RevenueFromContractWithCustomer...).
-- Keep the highest-priority tag from map_xbrl_tag; the chosen tag is kept as lineage.
create or replace table fact_financials as
with ranked as (
    select
        l.*,
        row_number() over (
            partition by cik, concept_code, period_start, period_end
            order by priority, tag
        ) as tag_rank,
        count(*) over (partition by cik, concept_code, period_start, period_end) as n_candidate_tags
    from int_facts_latest l
),
versions as (
    select cik, tag, period_start, period_end,
           count(distinct accn) as n_filings,
           count(distinct val)  as n_distinct_values
    from int_facts_versions
    group by all
)
select
    p.period_key,
    r.cik                         as company_key,
    c.concept_key,
    r.concept_code,
    r.val                         as value,
    r.tag                         as source_tag,
    r.n_candidate_tags,
    r.accn                        as source_accn,
    r.form                        as source_form,
    r.filed                       as source_filed,
    v.n_filings,
    v.n_distinct_values > 1       as is_restated
from ranked r
join dim_period  p on p.cik = r.cik
                  and p.period_end = r.period_end
                  and p.period_start is not distinct from r.period_start
join dim_concept c on c.concept_code = r.concept_code
join versions    v on v.cik = r.cik and v.tag = r.tag
                  and v.period_end = r.period_end
                  and v.period_start is not distinct from r.period_start
where r.tag_rank = 1;
