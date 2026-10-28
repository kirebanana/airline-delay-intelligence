"""One descriptor + validated filters -> bounded warehouse aggregates, never raw rows."""

import datetime as dt
import re
from dataclasses import dataclass

QUERY_VERSION = "primary-analytics-v2"
GROUPS = {
    "all": (),
    "carrier": ("marketing_carrier_id", "marketing_label"),
    "month": ("month_start",),
    "weekday": ("weekday",),
    "hour": ("scheduled_local_hour",),
    "airport": ("origin_id", "origin_label"),
    "route": ("origin_id", "origin_label", "destination_id", "destination_label"),
}


@dataclass(frozen=True)
class Filters:
    start: dt.date
    end: dt.date
    carriers: tuple[int, ...] = ()
    origin: int | None = None
    destination: int | None = None

    def __post_init__(self):
        if (
            type(self.start) is not dt.date
            or type(self.end) is not dt.date
            or not 0 <= (self.end - self.start).days <= 1461
        ):
            raise ValueError("Select an ordered bounded calendar window")
        ids = [*self.carriers, *[v for v in (self.origin, self.destination) if v is not None]]
        if len(self.carriers) > 50 or any(type(v) is not int or not 0 < v < 1_000_000 for v in ids):
            raise ValueError("Filters require positive stable numeric IDs, not SQL or codes")
        object.__setattr__(self, "carriers", tuple(sorted(set(self.carriers))))


def cache_identity(descriptor: dict, filters: Filters, group: str, minimum: int, limit: int):
    if group not in GROUPS or type(minimum) is not int or not 1 <= minimum <= 1_000_000:
        raise ValueError("Unknown grouping or ranking threshold")
    if type(limit) is not int or not 1 <= limit <= 2000:
        raise ValueError("Aggregate result limit must be 1–2000")
    return (
        "DC50202",
        "AIRLINE_DB",
        descriptor.get("target", "development"),
        descriptor["schema"],
        descriptor.get("release_id"),
        descriptor["processing_contract"],
        QUERY_VERSION,
        filters,
        group,
        minimum,
        limit,
    )


def relation(descriptor: dict, *, development=False) -> str:
    schema = descriptor["schema"]
    prefix = "WORK" if development else "RELEASE"
    if not descriptor.get("sealed") or not re.fullmatch(prefix + r"_[A-F0-9]{24}", schema):
        raise ValueError("A verified sealed descriptor is required; no arbitrary SQL relation")
    return f"AIRLINE_DB.{schema}." + ("FACT_FLIGHTS" if development else "FLIGHTS")


def query_metrics(
    connection,
    descriptor: dict,
    filters: Filters,
    group="all",
    *,
    minimum=100,
    limit=500,
    development=False,
) -> list[dict]:
    cache_identity(descriptor, filters, group, minimum, limit)
    table = relation(descriptor, development=development)
    conditions, parameters = ["flight_date>=%s", "flight_date<=%s"], [filters.start, filters.end]
    if filters.carriers:
        conditions.append(
            "marketing_carrier_id IN (" + ",".join(["%s"] * len(filters.carriers)) + ")"
        )
        parameters.extend(filters.carriers)
    for name, value in (("origin_id", filters.origin), ("destination_id", filters.destination)):
        if value is not None:
            conditions.append(name + "=%s")
            parameters.append(value)
    fields = GROUPS[group]
    leading = ", ".join(fields) + ", " if fields else ""
    grouping = " GROUP BY " + ", ".join(fields) if fields else ""
    sql = f"""SELECT {leading}COUNT(*) AS scheduled_rows,
COALESCE(COUNT_IF(arrival_eligible),0) AS arrival_denominator,
COALESCE(COUNT_IF(arrival_eligible AND arrival_delayed=0),0) AS arrival_numerator,
COALESCE(COUNT_IF(cancelled=1),0) AS cancellation_numerator,
COALESCE(COUNT_IF(diverted=1),0) AS diversion_numerator,
COALESCE(COUNT_IF(departure_eligible),0) AS departure_denominator,
COALESCE(COUNT_IF(departure_eligible AND departure_delayed=1),0) AS departure_numerator,
COALESCE(COUNT_IF(cancelled IS NULL),0) AS unknown_cancelled,
COALESCE(COUNT_IF(diverted IS NULL),0) AS unknown_diverted,
COALESCE(COUNT_IF(cancelled=0 AND diverted=0 AND arrival_delayed IS NULL),0) AS unknown_arrival,
COALESCE(COUNT_IF(cancelled=0 AND departure_delayed IS NULL),0) AS unknown_departure,
COALESCE(COUNT_IF(signed_arrival_eligible),0) AS signed_arrival_count,
AVG(IFF(signed_arrival_eligible,arrival_delay,NULL)) AS signed_mean,
PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY IFF(signed_arrival_eligible,arrival_delay,NULL))
    AS signed_median,
PERCENTILE_CONT(0.9) WITHIN GROUP(ORDER BY IFF(signed_arrival_eligible,arrival_delay,NULL))
    AS signed_p90,
arrival_numerator::DOUBLE/NULLIF(arrival_denominator,0) AS arrival_rate,
cancellation_numerator::DOUBLE/NULLIF(scheduled_rows,0) AS cancellation_rate,
diversion_numerator::DOUBLE/NULLIF(scheduled_rows,0) AS diversion_rate,
departure_numerator::DOUBLE/NULLIF(departure_denominator,0) AS departure_rate,
arrival_denominator>={minimum} AS arrival_rankable,
scheduled_rows>={minimum} AS schedule_rankable,
departure_denominator>={minimum} AS departure_rankable,
signed_arrival_count>={minimum} AS signed_rankable
FROM {table} WHERE {" AND ".join(conditions)}{grouping}
ORDER BY scheduled_rows DESC{(", " + ", ".join(fields)) if fields else ""} LIMIT %s"""
    with connection.cursor() as cur:
        cur.execute(sql, [*parameters, limit])
        return [
            dict(zip([c[0] for c in cur.description], row, strict=True)) for row in cur.fetchall()
        ]


def filter_options(connection, descriptor: dict, *, development=False) -> dict:
    table = relation(descriptor, development=development)
    with connection.cursor() as cur:
        cur.execute(f"SELECT MIN(flight_date),MAX(flight_date) FROM {table}")
        start, end = cur.fetchone()
        cur.execute(
            f"SELECT DISTINCT marketing_carrier_id,marketing_label FROM {table} "
            "ORDER BY marketing_carrier_id LIMIT 100"
        )
        carriers = cur.fetchall()
        cur.execute(
            f"SELECT DISTINCT origin_id,origin_label FROM {table} UNION "
            f"SELECT DISTINCT destination_id,destination_label FROM {table} "
            "ORDER BY 1 LIMIT 1000"
        )
        airports = cur.fetchall()
    return {"start": start, "end": end, "carriers": carriers, "airports": airports}
