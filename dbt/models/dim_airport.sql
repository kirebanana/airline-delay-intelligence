with versions as (
    select origin_id as airport_id, "Origin" as airport_code,
        "OriginAirportSeqID" as source_sequence, "OriginCityName" as city,
        "OriginStateName" as state_name, flight_date, "SOURCE_SHA256", "SOURCE_ROW_NUMBER"
    from {{ ref('stg_flights') }}
    union all
    select destination_id, "Dest", "DestAirportSeqID", "DestCityName", "DestStateName",
        flight_date, "SOURCE_SHA256", "SOURCE_ROW_NUMBER"
    from {{ ref('stg_flights') }}
)
select airport_id, airport_code, source_sequence, city, state_name
from versions
qualify row_number() over(partition by airport_id order by flight_date desc,
    "SOURCE_SHA256" desc,"SOURCE_ROW_NUMBER" desc,source_sequence desc,airport_code desc)=1
