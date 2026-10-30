{{ config(enabled=var('weather_enabled', false)) }}
select 'weather_population_or_mapping' as failure
from {{ ref('den_weather') }}
having count(*) <> (select count(*) from {{ ref('fact_flights') }}
                    where origin_id=11292 and flight_date>='2025-01-01' and flight_date<'2025-02-01')
    or count(*)=0 or count(*)<>count(distinct flight_key)
    or count_if(scheduled_utc is null)>0
    or coalesce(count_if(temperature_match_status='matched'),0)::double/count(*)<0.95
    or coalesce(count_if(wind_match_status='matched'),0)::double/count(*)<0.95
    or coalesce(count_if(visibility_match_status='matched'),0)::double/count(*)<0.95
union all
select 'weather_future_or_stale' from {{ ref('den_weather') }}
where (temperature_match_status='matched' and temperature_age_seconds not between 0 and 3600)
   or (wind_match_status='matched' and wind_age_seconds not between 0 and 3600)
   or (visibility_match_status='matched' and visibility_age_seconds not between 0 and 3600)
union all
select 'weather_duplicate_observation' from {{ ref('weather_observations') }}
group by station,variable,observed_at having count(*)<>1
