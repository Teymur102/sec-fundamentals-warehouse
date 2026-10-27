-- audit_restatements: every (company, tag, period) whose value changed between filings.
-- first_* = as originally filed, latest_* = what the warehouse uses.
create or replace table audit_restatements as
with keyed as (
    select *, strftime(filed, '%Y-%m-%d') || accn as version_key
    from int_facts_versions
),
agg as (
    select
        cik, concept_code, tag, period_type, period_start, period_end,
        arg_min(val,   version_key) as first_value,
        arg_min(form,  version_key) as first_form,
        arg_min(accn,  version_key) as first_accn,
        min(filed)                  as first_filed,
        arg_max(val,   version_key) as latest_value,
        arg_max(form,  version_key) as latest_form,
        arg_max(accn,  version_key) as latest_accn,
        max(filed)                  as latest_filed,
        count(distinct accn)        as n_filings,
        count(distinct val)         as n_distinct_values
    from keyed
    group by all
)
select
    a.*,
    d.ticker,
    a.latest_value - a.first_value                                               as change,
    case when a.first_value <> 0
         then (a.latest_value - a.first_value) / abs(a.first_value) end         as change_pct,
    case when a.first_value = 0 or abs((a.latest_value - a.first_value) / a.first_value) >= 0.005
         then 'material (>=0.5%)' else 'minor (<0.5%)' end                       as materiality,
    case when a.latest_form like '%/A'
         then 'amended filing' else 'recast in a later 10-K/10-Q' end           as restatement_source,
    exists (
        select 1 from fact_financials f
        join dim_period p using (period_key)
        where f.company_key = a.cik and f.source_tag = a.tag
          and p.period_end = a.period_end and p.period_start is not distinct from a.period_start
    )                                                                            as feeds_fact_table
from agg a
join dim_company d on d.cik = a.cik
where a.n_distinct_values > 1;
