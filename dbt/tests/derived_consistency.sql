-- Reconcile frozen analytical fields to native source values, not just raw hashes.
select f.flight_key
from {{ ref('fact_flights') }} f
left join {{ ref('dim_date') }} d on f.flight_date=d.date_key
left join {{ ref('dim_airport') }} o on f.origin_id=o.airport_id
left join {{ ref('dim_airport') }} a on f.destination_id=a.airport_id
left join {{ ref('dim_carrier') }} m on f.marketing_carrier_id=m.carrier_id
left join {{ ref('dim_carrier') }} p on f.operating_carrier_id=p.carrier_id
where f.flight_key is distinct from
        sha2('bts-marketing:' || f."SOURCE_SHA256" || ':' || f."SOURCE_ROW_NUMBER"::varchar,256)
 or f.flight_date is distinct from try_to_date(f."FlightDate")
 or f.origin_id is distinct from try_to_number(f."OriginAirportID")
 or f.destination_id is distinct from try_to_number(f."DestAirportID")
 or f.marketing_carrier_id is distinct from try_to_number(f."DOT_ID_Marketing_Airline")
 or f.operating_carrier_id is distinct from try_to_number(f."DOT_ID_Operating_Airline")
 or f.cancelled is distinct from try_to_double(nullif(f."Cancelled",''))
 or f.diverted is distinct from try_to_double(nullif(f."Diverted",''))
 or f.arrival_delayed is distinct from try_to_double(nullif(f."ArrDel15",''))
 or f.departure_delayed is distinct from try_to_double(nullif(f."DepDel15",''))
 or f.arrival_delay is distinct from try_to_double(nullif(f."ArrDelay",''))
 or f.departure_delay is distinct from try_to_double(nullif(f."DepDelay",''))
 or f.arrival_eligible is distinct from
        (try_to_double(f."Cancelled")=0 and try_to_double(f."Diverted")=0
         and try_to_double(nullif(f."ArrDel15",'')) in (0,1))
 or f.departure_eligible is distinct from
        (try_to_double(f."Cancelled")=0 and try_to_double(nullif(f."DepDel15",'')) in (0,1))
 or f.signed_arrival_eligible is distinct from
        (try_to_double(f."Cancelled")=0 and try_to_double(f."Diverted")=0
         and try_to_double(nullif(f."ArrDelay",'')) is not null)
 or f.scheduled_local_hour is distinct from
        (case when regexp_like(f."CRSDepTime",'[0-9]{1,4}')
         and try_to_number(f."CRSDepTime") between 0 and 2359
         and mod(try_to_number(f."CRSDepTime"),100) between 0 and 59
         then floor(try_to_number(f."CRSDepTime")/100)::integer end)
 or f.date_key is distinct from d.date_key
 or f.weekday is distinct from dayofweekiso(try_to_date(f."FlightDate"))
 or f.month_start is distinct from date_trunc('month',try_to_date(f."FlightDate"))::date
 or f.origin_label is distinct from o.airport_code
 or f.destination_label is distinct from a.airport_code
 or f.marketing_label is distinct from m.carrier_code
 or f.operating_label is distinct from p.carrier_code
