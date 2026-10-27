-- Every filing's version of every fact we map to a standard line item.
-- The period_type join drops mis-shaped facts (e.g. a balance-sheet tag reported as a duration).
-- seed_tag_overrides lets a reviewed, documented exception demote a tag for one company
-- (e.g. a filer whose "Revenues" tag is not its total revenue).
create or replace table int_facts_versions as
select
    s.*,
    m.concept_code,
    coalesce(o.priority, m.priority) as priority,
    o.reason                         as override_reason
from stg_facts s
join map_xbrl_tag m on m.tag = s.tag
join dim_concept  c on c.concept_code = m.concept_code and c.period_type = s.period_type
join dim_company  d on d.cik = s.cik
left join seed_tag_overrides o on o.ticker = d.ticker and o.tag = s.tag;

-- Dedupe step 1: one value per (company, tag, period) = the most recently filed one.
-- Ties on filing date are broken by accession number (later accession = later submission).
create or replace table int_facts_latest as
select * exclude (rn)
from (
    select
        v.*,
        row_number() over (
            partition by cik, tag, period_start, period_end
            order by filed desc, accn desc
        ) as rn
    from int_facts_versions v
)
where rn = 1;
