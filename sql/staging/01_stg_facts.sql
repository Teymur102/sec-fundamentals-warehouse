-- Staging: one row per fact per filing, typed and filtered to what the warehouse uses.
-- Grain: (cik, tag, period_start, period_end, accn). Nothing is deduplicated here on purpose:
-- the same number is re-reported in every later filing that shows it as a comparative,
-- and those repeats are exactly what the restatement audit needs.
create or replace table stg_facts as
select
    f.cik,
    f.tag,
    f.unit,
    f.period_start,
    f.period_end,
    case when f.period_start is null then 'instant' else 'duration' end            as period_type,
    case when f.period_start is null then null
         else date_diff('day', f.period_start, f.period_end) + 1 end               as duration_days,
    f.val,
    f.accn,
    f.fy                                                                           as filing_fy,  -- fiscal year of the FILING, not of the fact
    f.fp                                                                           as filing_fp,
    f.form,
    f.filed,
    f.frame
from raw_facts f
where f.taxonomy = 'us-gaap'
  and f.unit = 'USD'
  and f.form in ('10-K', '10-K/A', '10-Q', '10-Q/A', '10-KT', '10-KT/A');
