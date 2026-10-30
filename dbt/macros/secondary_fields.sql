{% macro secondary_fields() %}
    cancelled=0 and diverted=0 and arrival_delayed=1 as category_eligible,
    try_to_double(nullif("CarrierDelay",'')) as carrier_minutes,
    try_to_double(nullif("WeatherDelay",'')) as weather_minutes,
    try_to_double(nullif("NASDelay",'')) as nas_minutes,
    try_to_double(nullif("SecurityDelay",'')) as security_minutes,
    try_to_double(nullif("LateAircraftDelay",'')) as late_aircraft_minutes,
    category_eligible and carrier_minutes is not null and weather_minutes is not null
        and nas_minutes is not null and security_minutes is not null
        and late_aircraft_minutes is not null as category_complete,
    iff(category_complete, carrier_minutes+weather_minutes+nas_minutes+
        security_minutes+late_aircraft_minutes, null) as reported_minutes,
    iff(category_complete, arrival_delay-reported_minutes, null) as unallocated_minutes,
    cancelled=0 and diverted=0 and departure_delay>=15 and arrival_delay is not null
        as recovery_eligible,
    iff(recovery_eligible, departure_delay-arrival_delay, null) as signed_improvement,
    recovery_eligible and arrival_delay<15 as recovered_below_threshold,
    case when signed_improvement<0 then 'Worsened (<0)'
         when signed_improvement=0 then 'Unchanged (0)'
         when signed_improvement<15 then 'Improved (0–<15)'
         when signed_improvement<30 then 'Improved (15–<30)'
         when signed_improvement is not null then 'Improved (≥30)' end as recovery_band,
    case when cancelled=1 then case "CancellationCode"
         when 'A' then 'Carrier' when 'B' then 'Weather' when 'C' then 'NAS'
         when 'D' then 'Security' else 'Unknown / unrecognized' end end as cancellation_reason
{% endmacro %}
