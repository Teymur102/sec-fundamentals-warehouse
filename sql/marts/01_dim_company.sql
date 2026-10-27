-- Universe audit: every seed ticker, whether it made it in, and why not.
-- HQ state is taken from SEC's submissions endpoint (business address), not from memory.
create or replace table audit_universe as
select
    s.ticker,
    s.sector,
    s.industry_group,
    c.cik,
    c.entity_name,
    c.hq_city,
    c.hq_state,
    case
        when c.cik is null      then 'not in SEC company_tickers.json (delisted or taken private)'
        when c.hq_state <> 'MA' then 'business address is ' || c.hq_city || ', ' || c.hq_state || ' (not Massachusetts)'
    end as exclusion_reason
from seed_companies s
left join raw_companies c
       on list_contains(string_split(c.tickers, ','), s.ticker);

-- dim_company: one row per included company.
-- company_type drives which ratios are meaningful (see sql/analytics).
create or replace table dim_company as
select
    c.cik                                   as company_key,
    c.cik,
    u.ticker,
    c.entity_name,
    u.sector,
    u.industry_group,
    c.sic,
    c.sic_description,
    case
        when c.sic between 6000 and 6099 then 'bank'
        when c.sic between 6300 and 6411 then 'insurer'
        when c.sic = 6798                then 'reit'
        else 'operating'
    end                                     as company_type,
    c.hq_city,
    c.hq_state,
    c.fiscal_year_end_mmdd
from audit_universe u
join raw_companies c on c.cik = u.cik
where u.exclusion_reason is null;
