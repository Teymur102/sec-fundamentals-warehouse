-- dim_concept: the standard line items the warehouse reports on (one row each).
create or replace table dim_concept as
select
    row_number() over (order by statement, concept_code) as concept_key,
    concept_code,
    line_item,
    statement,
    period_type,
    description
from seed_concepts;

-- map_xbrl_tag: many XBRL tags -> one standard line item, with a priority.
-- Example: revenue <- Revenues (1), RevenueFromContractWithCustomerExcludingAssessedTax (2), SalesRevenueNet (4) ...
create or replace table map_xbrl_tag as
select tag, concept_code, priority, note
from seed_tag_map;
