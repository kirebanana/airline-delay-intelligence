select distinct flight_date as date_key, year(flight_date) as year,
    month(flight_date) as month, dayofweekiso(flight_date) as weekday,
    date_trunc('month',flight_date)::date as month_start
from {{ ref('stg_flights') }}
