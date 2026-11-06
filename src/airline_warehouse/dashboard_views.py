"""Presentation shaping only: warehouse counts/rates/quantiles remain authoritative."""

import calendar
import datetime as dt

TASKS = [
    "Network & carriers",
    "Time & routes",
    "Disruption & recovery",
    "DEN weather investigation",
]
RECOVERY_ORDER = [
    "Worsened (<0)",
    "Unchanged (0)",
    "Improved (0–<15)",
    "Improved (15–<30)",
    "Improved (≥30)",
]
RATES = {
    "Arrival on-time": ("ARRIVAL_RATE", "ARRIVAL_DENOMINATOR"),
    "Cancellation": ("CANCELLATION_RATE", "SCHEDULED_ROWS"),
    "Diversion": ("DIVERSION_RATE", "SCHEDULED_ROWS"),
    "Departure delay ≥15 min": ("DEPARTURE_RATE", "DEPARTURE_DENOMINATOR"),
}


def number(value, suffix="", decimals=0):
    return "N/A" if value is None else f"{float(value):,.{decimals}f}{suffix}"


def percent(value):
    return "N/A" if value is None else f"{float(value):.1%}"


def group_label(row, group):
    if group == "carrier":
        return row["MARKETING_LABEL"]
    if group == "airport":
        return row["ORIGIN_LABEL"]
    if group == "route":
        return f"{row['ORIGIN_LABEL']} → {row['DESTINATION_LABEL']}"
    if group == "month":
        return str(row["MONTH_START"])[:7]
    if group == "weekday":
        return calendar.day_name[int(row["WEEKDAY"]) - 1]
    hour = int(row["SCHEDULED_LOCAL_HOUR"])
    return "Source 2400" if hour == 24 else f"{hour:02}:00"


def ordered_rows(rows, group):
    field = {"month": "MONTH_START", "weekday": "WEEKDAY", "hour": "SCHEDULED_LOCAL_HOUR"}.get(
        group
    )
    return sorted(rows, key=lambda r: r[field]) if field else list(rows)


def comparison_table(rows, group):
    def rate(v):
        return None if v is None else float(v) * 100

    return [
        {
            "Group": group_label(r, group),
            "Scheduled": r["SCHEDULED_ROWS"],
            "On-time": rate(r["ARRIVAL_RATE"]),
            "Cancelled": rate(r["CANCELLATION_RATE"]),
            "Diverted": rate(r["DIVERSION_RATE"]),
            "Departure delayed": rate(r["DEPARTURE_RATE"]),
            "Median min": None if r["SIGNED_MEDIAN"] is None else float(r["SIGNED_MEDIAN"]),
            "p90 min": None if r["SIGNED_P90"] is None else float(r["SIGNED_P90"]),
            "Arrival eligible": r["ARRIVAL_DENOMINATOR"],
            "Departure eligible": r["DEPARTURE_DENOMINATOR"],
            "Signed eligible": r["SIGNED_ARRIVAL_COUNT"],
        }
        for r in ordered_rows(rows, group)
    ]


def prior_year(filters, start, end):
    """Same inclusive calendar dates last year; leap day clamps to Feb 28."""
    from dataclasses import replace

    def shift(d):
        return dt.date(d.year - 1, d.month, min(d.day, calendar.monthrange(d.year - 1, d.month)[1]))

    a, b = shift(filters.start), shift(filters.end)
    return replace(filters, start=a, end=b) if start <= a <= b <= end else None


def weather_support(row, minimum):
    return (
        row["LOCAL_DATES"] >= 5,
        row["SCHEDULED_ROWS"] >= minimum,
        row["DEPARTURE_DENOMINATOR"] >= minimum,
    )
