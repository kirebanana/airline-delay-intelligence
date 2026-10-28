-- Critical contract checks: unknown flags are not false; missing indicators are exclusions.
select 'invalid_row' as failure from {{ ref('fact_flights') }}
where flight_date is null or scheduled_local_hour is null
   or cancelled is null or cancelled not in (0,1)
   or diverted is null or diverted not in (0,1)
   or ("ArrDel15"<>'' and (arrival_delayed is null or arrival_delayed not in (0,1)))
   or ("DepDel15"<>'' and (departure_delayed is null or departure_delayed not in (0,1)))
   or ("ArrDelay"<>'' and arrival_delay is null)
   or ("DepDelay"<>'' and departure_delay is null)
   or ("ArrDelay"<>'' and not regexp_like("ArrDelay",'[-+]?[0-9]+([.][0-9]+)?'))
   or ("DepDelay"<>'' and not regexp_like("DepDelay",'[-+]?[0-9]+([.][0-9]+)?'))
   or not regexp_like("OriginAirportID",'[0-9]+')
   or not regexp_like("DestAirportID",'[0-9]+')
   or not regexp_like("DOT_ID_Marketing_Airline",'[0-9]+')
   or not regexp_like("DOT_ID_Operating_Airline",'[0-9]+')
   or origin_id is null or destination_id is null or marketing_carrier_id is null
   or operating_carrier_id is null or date_key is null or origin_label is null
   or destination_label is null or marketing_label is null or operating_label is null
   or origin_id<=0 or destination_id<=0 or marketing_carrier_id<=0 or operating_carrier_id<=0
   or origin_label='' or destination_label='' or marketing_label='' or operating_label=''
union all
select 'count_mismatch' from {{ ref('fact_flights') }}
having count(*) <> {{ var('expected_rows',0) }}
union all
select 'stage_count_mismatch' from {{ ref('stg_flights') }}
having count(*) <> {{ var('expected_rows',0) }}
