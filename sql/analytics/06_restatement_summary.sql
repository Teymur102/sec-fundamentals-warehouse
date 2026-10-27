-- restatement_summary: per company, how many reported values changed after first filing.
create or replace table restatement_summary as
select
    ticker,
    count(*)                                                           as restated_values,
    count(*) filter (where materiality like 'material%')               as material,
    count(*) filter (where restatement_source = 'amended filing')      as via_amendment,
    count(*) filter (where feeds_fact_table)                           as feeding_fact_table,
    max(abs(change_pct)) filter (where first_value <> 0)               as max_abs_change_pct
from audit_restatements
group by ticker
order by restated_values desc, ticker;
