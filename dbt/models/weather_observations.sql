{{ config(enabled=var('weather_enabled', false)) }}
select parse_json(record):station::varchar as station,
       parse_json(record):variable::varchar as variable,
       to_timestamp_ntz(parse_json(record):observed_at::varchar) as observed_at,
       parse_json(record):value::double as value,
       parse_json(record):status::varchar as status,
       parse_json(record):provenance as provenance,
       parse_json(record):duplicate_count::integer as duplicate_count,
       record as preserved_record
from {{ source('selected_input','selected_weather') }}
