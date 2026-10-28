select r.*,
    sha2('bts-marketing:' || "SOURCE_SHA256" || ':' || "SOURCE_ROW_NUMBER"::varchar,256) as flight_key,
    try_to_date("FlightDate") as flight_date,
    try_to_number("OriginAirportID") as origin_id,
    try_to_number("DestAirportID") as destination_id,
    try_to_number("DOT_ID_Marketing_Airline") as marketing_carrier_id,
    try_to_number("DOT_ID_Operating_Airline") as operating_carrier_id,
    try_to_double(nullif("Cancelled",'')) as cancelled,
    try_to_double(nullif("Diverted",'')) as diverted,
    try_to_double(nullif("ArrDel15",'')) as arrival_delayed,
    try_to_double(nullif("DepDel15",'')) as departure_delayed,
    try_to_double(nullif("ArrDelay",'')) as arrival_delay,
    try_to_double(nullif("DepDelay",'')) as departure_delay,
    case when regexp_like("CRSDepTime",'[0-9]{1,4}')
         and try_to_number("CRSDepTime") between 0 and 2359
         and mod(try_to_number("CRSDepTime"),100) between 0 and 59
         then floor(try_to_number("CRSDepTime")/100)::integer end as scheduled_local_hour,
    cancelled=0 and diverted=0 and arrival_delayed in (0,1) as arrival_eligible,
    cancelled=0 and departure_delayed in (0,1) as departure_eligible,
    cancelled=0 and diverted=0 and arrival_delay is not null as signed_arrival_eligible
from {{ source('selected_input','selected_raw') }} r
