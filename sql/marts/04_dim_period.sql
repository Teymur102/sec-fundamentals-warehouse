-- Fiscal calendar. Company-specific, because fiscal years are:
--   TJX's year ending 2026-01-31 is "fiscal 2026"; BJ's year ending 2026-01-31 is "fiscal 2025".
--
-- SEC's `fy` field belongs to the FILING, not the fact: a FY2025 10-K also carries FY2024 and
-- FY2023 comparatives, all stamped fy=2025. So we cannot read fiscal year off each fact.
-- Instead:
--   1. For each 10-K, its own period = the latest one-year duration it reports.
--   2. Per company, learn the offset between the filing's fy and year(period_end - 15 days),
--      taken from the MOST RECENT 10-K, i.e. the company's current naming convention.
--      (The 15-day shift folds 52/53-week years that end on Jan 1-3 back into the prior year.)
--      Why the latest and not the most common: TJX tagged its year ended 2021-01-30 as fy 2020
--      but its year ended 2022-01-29 as fy 2022 - it switched conventions, so 2021 never appears.
--   3. Apply that offset to every one-year period the company has ever reported.
--      Check 12 lists every older filing whose own fy label disagrees with the result.

create or replace table int_primary_10k as
select
    cik,
    accn,
    max(filing_fy)  as filing_fy,
    max(period_end) as doc_period_end
from int_facts_versions
where form in ('10-K', '10-K/A', '10-KT', '10-KT/A')
  and period_type = 'duration'
  and duration_days between 350 and 380
group by cik, accn;

create or replace table int_fy_offset as
select
    cik,
    arg_max(filing_fy - year(doc_period_end - interval 15 day), doc_period_end) as fy_offset
from int_primary_10k
group by cik;

create or replace table int_fy_ends as
select distinct
    p.cik,
    p.period_end                                              as fy_end,
    year(p.period_end - interval 15 day) + o.fy_offset        as fiscal_year
from int_facts_latest p
join int_fy_offset o using (cik)
where p.period_type = 'duration'
  and p.duration_days between 350 and 380;

create or replace table dim_period as
with periods as (
    select distinct cik, period_type, period_start, period_end, duration_days
    from int_facts_latest
),
-- fiscal year of any date = fiscal year of the first fiscal-year end on/after it
next_fy as (
    select p.cik, p.period_start, p.period_end,
           arg_min(e.fiscal_year, e.fy_end) as fiscal_year
    from periods p
    join int_fy_ends e on e.cik = p.cik and e.fy_end >= p.period_end - interval 7 day
    group by all
),
prev_fy as (
    select p.cik, p.period_start, p.period_end,
           max(e.fy_end) as prev_fy_end
    from periods p
    join int_fy_ends e on e.cik = p.cik and e.fy_end < p.period_end - interval 7 day
    group by all
),
last_fy as (
    select cik, max(fy_end) as last_fy_end, max(fiscal_year) as last_fiscal_year
    from int_fy_ends group by cik
)
select
    md5(p.cik::varchar || '|' || coalesce(p.period_start::varchar, '') || '|' || p.period_end::varchar) as period_key,
    p.cik,
    p.period_type,
    p.period_start,
    p.period_end,
    p.duration_days,
    case
        when p.period_type = 'instant'           then 'instant'
        when p.duration_days between 350 and 380 then 'FY'
        when p.duration_days between 84 and 98   then 'Q'
        else 'YTD/other'
    end                                                                 as period_length,
    coalesce(
        n.fiscal_year,
        -- periods after the last 10-K (current year in progress, from 10-Qs)
        case when p.period_end <= l.last_fy_end + interval 380 day then l.last_fiscal_year + 1 end
    )                                                                   as fiscal_year,
    case
        when p.period_type = 'duration' and p.duration_days not between 84 and 98 then null
        when pf.prev_fy_end is null then null
        else least(4, greatest(1, round(date_diff('day', pf.prev_fy_end, p.period_end) / 91.3)::integer))
    end                                                                 as fiscal_quarter,
    exists (select 1 from int_fy_ends e where e.cik = p.cik and e.fy_end = p.period_end) as is_fiscal_year_end
from periods p
left join next_fy n on n.cik = p.cik and n.period_end = p.period_end and n.period_start is not distinct from p.period_start
left join prev_fy pf on pf.cik = p.cik and pf.period_end = p.period_end and pf.period_start is not distinct from p.period_start
left join last_fy l on l.cik = p.cik;
