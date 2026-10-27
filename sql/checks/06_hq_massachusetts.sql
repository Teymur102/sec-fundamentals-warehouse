-- name: Universe is Massachusetts-headquartered
-- severity: error
-- description: Every company in dim_company has an MA business address in SEC submissions data.
-- population: select count(*) from dim_company
select ticker, entity_name, hq_city, hq_state from dim_company where hq_state is distinct from 'MA';
