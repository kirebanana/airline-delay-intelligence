"""One descriptor + validated filters -> bounded warehouse aggregates, never raw rows."""

import datetime as dt
import re
from dataclasses import dataclass

QUERY_VERSION = "categories-recovery-weather-v4"
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
    conditions, parameters = filter_predicate(filters)
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
        airport_table = table.rsplit(".", 1)[0] + (".DIM_AIRPORT" if development else ".AIRPORTS")
        cur.execute(
            f"SELECT airport_id,airport_code,city FROM {airport_table} "
            "ORDER BY airport_id LIMIT 1000"
        )
        airport_locations = cur.fetchall()
    return {
        "start": start,
        "end": end,
        "carriers": carriers,
        "airports": airports,
        "airport_locations": airport_locations,
    }


def filter_predicate(filters: Filters):
    conditions = ["flight_date>=%s", "flight_date<=%s"]
    parameters = [filters.start, filters.end]
    if filters.carriers:
        conditions.append(
            "marketing_carrier_id IN (" + ",".join(["%s"] * len(filters.carriers)) + ")"
        )
        parameters.extend(filters.carriers)
    for name, value in (("origin_id", filters.origin), ("destination_id", filters.destination)):
        if value is not None:
            conditions.append(name + "=%s")
            parameters.append(value)
    return conditions, parameters


def query_secondary(connection, descriptor, filters, *, development=False):
    """Filtered flight values -> compatible category subsets and signed recovery.

    Eligibility, units, reason labels and histogram bands are dbt fields. Only
    bounded aggregate results cross this seam; missing categories are not zero.
    """
    table = relation(descriptor, development=development)
    conditions, parameters = filter_predicate(filters)
    scope = f"WITH selected AS (SELECT * FROM {table} WHERE {' AND '.join(conditions)}) "

    def read(sql):
        with connection.cursor() as cur:
            cur.execute(scope + sql, parameters)
            return [
                dict(zip([c[0] for c in cur.description], r, strict=True)) for r in cur.fetchall()
            ]

    summary = read("""SELECT COUNT(*) AS scheduled_rows,
        COALESCE(COUNT_IF(category_eligible),0) AS category_eligible,
        COALESCE(COUNT_IF(category_complete),0) AS category_complete,
        COALESCE(COUNT_IF(category_eligible),0)-COALESCE(COUNT_IF(category_complete),0)
            AS missing_category_rows,
        SUM(IFF(category_eligible AND NOT category_complete,arrival_delay,NULL))
            AS excluded_arrival_minutes,
        COALESCE(SUM(unallocated_minutes),0) AS unallocated_minutes,
        COALESCE(COUNT_IF(category_complete AND ABS(unallocated_minutes)>0.000001),0)
            AS allocation_mismatch_rows,
        SUM(reported_minutes) AS reported_category_minutes,
        SUM(IFF(category_complete,arrival_delay,NULL)) AS complete_arrival_minutes,
        COALESCE(COUNT_IF(recovery_eligible),0) AS recovery_eligible,
        COALESCE(COUNT_IF(cancelled=0 AND diverted=0 AND departure_delay>=15
            AND arrival_delay IS NULL),0) AS recovery_missing_arrival,
        COALESCE(COUNT_IF(cancelled=0 AND diverted=0 AND departure_delay IS NULL),0)
            AS recovery_missing_departure,
        COALESCE(COUNT_IF(recovered_below_threshold),0) AS recovered,
        COALESCE(COUNT_IF(recovered_below_threshold),0)::DOUBLE/
            NULLIF(COUNT_IF(recovery_eligible),0) AS recovery_share,
        AVG(signed_improvement) AS improvement_mean,
        PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY signed_improvement) AS improvement_median,
        PERCENTILE_CONT(0.9) WITHIN GROUP(ORDER BY signed_improvement) AS improvement_p90
        FROM selected""")[0]
    categories = []
    for label, field in (
        ("Carrier", "carrier_minutes"),
        ("Weather", "weather_minutes"),
        ("NAS", "nas_minutes"),
        ("Security", "security_minutes"),
        ("Late aircraft", "late_aircraft_minutes"),
    ):
        row = read(f"""SELECT SUM(IFF(category_complete,{field},NULL)) AS reported_minutes,
            COALESCE(COUNT_IF(category_complete AND {field}>0),0) AS affected_rows,
            COALESCE(COUNT_IF(category_complete),0) AS eligible_complete_late_arrivals,
            affected_rows::DOUBLE/NULLIF(eligible_complete_late_arrivals,0) AS affected_rate,
            SUM(IFF(category_complete,{field},NULL))::DOUBLE/
                NULLIF(SUM(selected.reported_minutes),0) AS minute_share
            FROM selected""")[0]
        categories.append({"CATEGORY": label, **row})
    return {
        "summary": summary,
        "categories": categories,
        "cancellations": read("""SELECT cancellation_reason,COUNT(*) AS cancelled_rows,
            COUNT(*)::DOUBLE/NULLIF(SUM(COUNT(*)) OVER(),0) AS cancelled_share
            FROM selected WHERE cancelled=1 GROUP BY cancellation_reason
            ORDER BY cancelled_rows DESC"""),
        "distribution": read("""SELECT recovery_band,COUNT(*) AS eligible_rows
            FROM selected WHERE recovery_eligible GROUP BY recovery_band ORDER BY recovery_band"""),
    }


def query_weather(connection, descriptor, filters, *, development=False, details=True):
    relation(descriptor, development=development)
    if not descriptor.get("weather"):
        raise ValueError("This release does not contain the qualified fixed weather pilot")
    table = f"AIRLINE_DB.{descriptor['schema']}." + ("DEN_WEATHER" if development else "WEATHER")
    conditions, parameters = filter_predicate(filters)
    scope = f"SELECT * FROM {table} WHERE {' AND '.join(conditions)}"

    def read(sql, values):
        with connection.cursor() as cur:
            cur.execute(sql, values)
            return [
                dict(zip([c[0] for c in cur.description], row, strict=True))
                for row in cur.fetchall()
            ]

    def coverage(selected, values):
        results = []
        for v in ("temperature", "wind", "visibility"):
            results.extend(
                {"VARIABLE": v, **row}
                for row in read(
                    f"""
                SELECT cancelled,COUNT(*) AS scheduled_rows,
                COALESCE(COUNT_IF({v}_match_status='matched'),0) AS matched_rows,
                matched_rows::DOUBLE/NULLIF(scheduled_rows,0) AS coverage,
                COALESCE(COUNT_IF({v}_match_status='stale'),0) AS stale_rows,
                COALESCE(COUNT_IF({v}_match_status='no_prior_accepted'),0) AS no_prior_accepted,
                COALESCE(COUNT_IF({v}_match_status IN ('mapping_or_time',
                    'ambiguous_local_time','nonexistent_local_time','unresolved_midnight')),0)
                    AS mapping_or_time,
                COALESCE(COUNT_IF({v}_newest_status='rejected_qc'),0) AS newest_rejected_qc,
                COALESCE(COUNT_IF({v}_newest_status='missing'),0) AS newest_missing,
                COALESCE(COUNT_IF({v}_newest_status='malformed'),0) AS newest_malformed,
                COALESCE(COUNT_IF({v}_older_good_fallback),0) AS older_good_fallback,
                AVG(IFF({v}_match_status='matched',{v}_age_seconds,NULL))
                    AS mean_matched_age_seconds,
                MAX(IFF({v}_match_status='matched',{v}_age_seconds,NULL)) AS max_matched_age_seconds
                FROM ({selected}) GROUP BY cancelled ORDER BY cancelled""",
                    values,
                )
            )
        return results

    comparisons, daily = [], []
    for v in ("temperature", "wind", "visibility"):
        comparisons.extend(
            {"VARIABLE": v, **row}
            for row in read(
                f"""
            WITH daily AS (SELECT {v}_band AS band,flight_date,COUNT(*) AS scheduled_rows,
                COALESCE(COUNT_IF(cancelled=1),0) AS cancelled_rows,
                COALESCE(COUNT_IF(departure_eligible),0) AS departure_denominator,
                COALESCE(COUNT_IF(departure_eligible AND departure_delayed=1),0) AS delayed_rows
                FROM ({scope}) GROUP BY {v}_band,flight_date)
            SELECT band,SUM(scheduled_rows) AS scheduled_rows,COUNT(*) AS local_dates,
                MAX(daily.scheduled_rows)::DOUBLE/NULLIF(SUM(daily.scheduled_rows),0)
                    AS largest_date_share,
                SUM(cancelled_rows) AS cancelled_rows,
                SUM(cancelled_rows)::DOUBLE/NULLIF(SUM(daily.scheduled_rows),0)
                    AS cancellation_rate,
                SUM(departure_denominator) AS departure_denominator,
                SUM(delayed_rows) AS delayed_rows,
                SUM(delayed_rows)::DOUBLE/NULLIF(SUM(departure_denominator),0)
                    AS departure_delay_rate
            FROM daily GROUP BY band ORDER BY band""",
                parameters,
            )
        )
        if details:
            daily.extend(
                {"VARIABLE": v, **row}
                for row in read(
                    f"""
            SELECT flight_date,COUNT(*) AS scheduled_rows,
                COALESCE(COUNT_IF({v}_match_status='matched'),0) AS matched_rows
            FROM ({scope}) GROUP BY flight_date ORDER BY flight_date""",
                    parameters,
                )
            )
    return {
        "pilot_coverage": coverage(f"SELECT * FROM {table}", []) if details else [],
        "selected_coverage": coverage(scope, parameters),
        "comparisons": comparisons,
        "daily": daily,
    }
