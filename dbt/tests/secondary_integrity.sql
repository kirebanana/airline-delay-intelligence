-- Missing allocations are disclosed exclusions; malformed/negative or new complete
-- reconciliation failures block. The exception is exactly the reviewed source row.
select flight_key from {{ ref('fact_flights') }}
where category_eligible is distinct from (cancelled=0 and diverted=0 and arrival_delayed=1)
 or carrier_minutes is distinct from try_to_double(nullif("CarrierDelay",''))
 or weather_minutes is distinct from try_to_double(nullif("WeatherDelay",''))
 or nas_minutes is distinct from try_to_double(nullif("NASDelay",''))
 or security_minutes is distinct from try_to_double(nullif("SecurityDelay",''))
 or late_aircraft_minutes is distinct from try_to_double(nullif("LateAircraftDelay",''))
 or ("CarrierDelay"<>'' and not regexp_like("CarrierDelay",'[0-9]+([.][0-9]+)?'))
 or ("WeatherDelay"<>'' and not regexp_like("WeatherDelay",'[0-9]+([.][0-9]+)?'))
 or ("NASDelay"<>'' and not regexp_like("NASDelay",'[0-9]+([.][0-9]+)?'))
 or ("SecurityDelay"<>'' and not regexp_like("SecurityDelay",'[0-9]+([.][0-9]+)?'))
 or ("LateAircraftDelay"<>'' and not regexp_like("LateAircraftDelay",'[0-9]+([.][0-9]+)?'))
 or category_complete is distinct from (category_eligible and carrier_minutes is not null
    and weather_minutes is not null and nas_minutes is not null
    and security_minutes is not null and late_aircraft_minutes is not null)
 or reported_minutes is distinct from iff(category_complete,
    carrier_minutes+weather_minutes+nas_minutes+security_minutes+late_aircraft_minutes,null)
 or unallocated_minutes is distinct from iff(category_complete,arrival_delay-reported_minutes,null)
 or (category_complete and (arrival_delay is null or abs(unallocated_minutes)>0.000001)
     and not ("SOURCE_SHA256"='7a96466f2165b93ac1a064422c960e9b3089c2cc8a70c2cbabc8fde1c8b0af31'
          and "SOURCE_ROW_NUMBER"=432835
          and "SOURCE_ROW_SHA256"='6f5f8a19f8c3d65e1e0a064a5660985b4c13206709083c7cc41f7eefe6a9699c'))
 or recovery_eligible is distinct from
    (cancelled=0 and diverted=0 and departure_delay>=15 and arrival_delay is not null)
 or signed_improvement is distinct from iff(recovery_eligible,departure_delay-arrival_delay,null)
 or recovered_below_threshold is distinct from (recovery_eligible and arrival_delay<15)
 or recovery_band is distinct from
    (case when signed_improvement<0 then 'Worsened (<0)'
          when signed_improvement=0 then 'Unchanged (0)'
          when signed_improvement<15 then 'Improved (0–<15)'
          when signed_improvement<30 then 'Improved (15–<30)'
          when signed_improvement is not null then 'Improved (≥30)' end)
 or cancellation_reason is distinct from
    (case when cancelled=1 then case "CancellationCode"
          when 'A' then 'Carrier' when 'B' then 'Weather' when 'C' then 'NAS'
          when 'D' then 'Security' else 'Unknown / unrecognized' end end)
