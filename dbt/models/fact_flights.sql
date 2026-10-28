select s.*, d.date_key, d.weekday, d.month_start,
    o.airport_code as origin_label, a.airport_code as destination_label,
    m.carrier_code as marketing_label, p.carrier_code as operating_label
from {{ ref('stg_flights') }} s
left join {{ ref('dim_date') }} d on s.flight_date=d.date_key
left join {{ ref('dim_airport') }} o on s.origin_id=o.airport_id
left join {{ ref('dim_airport') }} a on s.destination_id=a.airport_id
left join {{ ref('dim_carrier') }} m on s.marketing_carrier_id=m.carrier_id
left join {{ ref('dim_carrier') }} p on s.operating_carrier_id=p.carrier_id
