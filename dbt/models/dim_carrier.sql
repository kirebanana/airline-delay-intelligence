with versions as (
    select marketing_carrier_id as carrier_id, "Marketing_Airline_Network" as carrier_code,
        flight_date, "SOURCE_SHA256", "SOURCE_ROW_NUMBER"
    from {{ ref('stg_flights') }}
    union all
    select operating_carrier_id, "Operating_Airline", flight_date,
        "SOURCE_SHA256", "SOURCE_ROW_NUMBER" from {{ ref('stg_flights') }}
)
select carrier_id, carrier_code from versions
qualify row_number() over(partition by carrier_id order by flight_date desc,
    "SOURCE_SHA256" desc,"SOURCE_ROW_NUMBER" desc,carrier_code desc)=1
