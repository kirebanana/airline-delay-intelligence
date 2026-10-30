{{ config(enabled=var('weather_enabled', false)) }}
-- One row per scheduled pilot source row. No actual/cancellation event anchor.
with anchors as (
    select flight_key, flight_date, marketing_carrier_id, origin_id, destination_id,
           cancelled, diverted, departure_eligible, departure_delayed,
           "FlightDate" as source_date, "CRSDepTime" as source_clock,
           "OriginAirportSeqID" as source_origin_sequence,
           '72565003017' as station,
           case when "Origin"='DEN' and "OriginAirportSeqID"='1129202'
                 and regexp_like("CRSDepTime",'[0-9]{1,4}')
                 and try_to_number("CRSDepTime") between 1 and 2359
                 and mod(try_to_number("CRSDepTime"),100)<60 then
               convert_timezone('America/Denver','UTC',
                   dateadd(minute, mod(try_to_number("CRSDepTime"),100),
                       dateadd(hour, floor(try_to_number("CRSDepTime")/100),
                           flight_date::timestamp_ntz))) end as scheduled_utc
    from {{ ref('fact_flights') }}
    where origin_id=11292 and flight_date>='2025-01-01' and flight_date<'2025-02-01'
),
{% for v in ['temperature','wind','visibility'] %}
{{ v }}_raw as (select * from {{ ref('weather_observations') }} where variable='{{ v }}'),
{{ v }}_good as (select * from {{ v }}_raw where status='accepted'){{ ',' if not loop.last }}
{% endfor %}
select a.*,
{% for v in ['temperature','wind','visibility'] %}
       {{ v }}.observed_at as {{ v }}_observed_at,
       datediff(second,{{ v }}.observed_at,a.scheduled_utc) as {{ v }}_age_seconds,
       case when a.scheduled_utc is null then 'mapping_or_time'
            when {{ v }}.observed_at is null then 'no_prior_accepted'
            when {{ v }}_age_seconds>3600 then 'stale'
            else 'matched' end as {{ v }}_match_status,
       iff({{ v }}_match_status='matched',{{ v }}.value,null) as {{ v }}_value,
       newest_{{ v }}.observed_at as {{ v }}_newest_at,
       newest_{{ v }}.status as {{ v }}_newest_status,
       {{ v }}_match_status='matched' and {{ v }}.observed_at<newest_{{ v }}.observed_at
           as {{ v }}_older_good_fallback,
       {{ v }}.provenance as {{ v }}_provenance,
       case when {{ v }}_match_status<>'matched' then 'Unmatched'
       {% if v=='temperature' %}
            when {{ v }}_value< -10 then '<−10 °C'
            when {{ v }}_value<0 then '−10–<0 °C' else '≥0 °C'
       {% elif v=='wind' %}
            when {{ v }}_value<5 then '<5 m/s'
            when {{ v }}_value<10 then '5–<10 m/s' else '≥10 m/s'
       {% else %}
            when {{ v }}_value<1600 then '<1600 m'
            when {{ v }}_value<5000 then '1600–<5000 m' else '≥5000 m'
       {% endif %}
       end as {{ v }}_band{{ ',' if not loop.last }}
{% endfor %}
from anchors a
{% for v in ['temperature','wind','visibility'] %}
asof join {{ v }}_good {{ v }} match_condition(a.scheduled_utc>={{ v }}.observed_at)
    on a.station={{ v }}.station
asof join {{ v }}_raw newest_{{ v }} match_condition(a.scheduled_utc>=newest_{{ v }}.observed_at)
    on a.station=newest_{{ v }}.station
{% endfor %}
