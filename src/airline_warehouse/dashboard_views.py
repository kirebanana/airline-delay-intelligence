"""Presentation shaping only: warehouse counts/rates/quantiles remain authoritative."""

import calendar
import datetime as dt
import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files

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


def percent_value(value):
    """Numeric percentage points for sortable cells; format only at the column layer."""
    return None if value is None else float(value) * 100


def sort_comparisons(rows, group, field, denominator, minimum, order):
    """Sort displayed comparisons, keeping missing/low-support rates last."""
    if order == "Most flights":
        return sorted(rows, key=lambda r: (-r["SCHEDULED_ROWS"], group_label(r, group)))
    if order == "Name (A–Z)":
        return sorted(rows, key=lambda r: group_label(r, group))

    def key(row):
        supported = row[field] is not None and row[denominator] >= minimum
        value = float(row[field]) if supported else 0
        return (
            not supported,
            -value if order == "Highest rate first" else value,
            group_label(row, group),
        )

    return sorted(rows, key=key)


def arrival_timing(value):
    if value is None:
        return "N/A"
    if float(value) == 0:
        return "On schedule"
    return f"{abs(float(value)):.1f} min {'early' if value < 0 else 'late'}"


WEATHER_BANDS = {
    "temperature": ["<−10 °C", "−10–<0 °C", "≥0 °C", "Unmatched"],
    "wind": ["<5 m/s", "5–<10 m/s", "≥10 m/s", "Unmatched"],
    "visibility": ["<1600 m", "1600–<5000 m", "≥5000 m", "Unmatched"],
}


@dataclass(frozen=True)
class WeatherCoverage:
    start: dt.date
    end: dt.date  # inclusive local source dates, unlike manifest's exclusive end
    origin_id: int = 11292

    @property
    def label(self):
        if self.start.day == 1 and self.end == dt.date(
            self.start.year,
            self.start.month,
            calendar.monthrange(self.start.year, self.start.month)[1],
        ):
            return self.start.strftime("%B %Y")
        if self.start == dt.date(self.start.year, 1, 1) and self.end == dt.date(
            self.end.year, 12, 31
        ):
            return f"{self.start.year}–{self.end.year}"
        return f"{self.start:%d %b %Y} – {self.end:%d %b %Y}"


def weather_coverage(manifest):
    """Presentation-only scope allowlist; never infer weather dates from flight dates.

    Legacy UTC observation bounds include lookback and are not local flight dates.
    Only that known contract may omit explicit local scope metadata.
    """
    if not isinstance(manifest, dict) or manifest.get("origin_id") != 11292:
        return None
    contract = manifest.get("contract")
    if contract == "den-isd-aviation-qc15-independent-60m-v1":
        station, earliest, latest = "72565003017", dt.date(2025, 1, 1), dt.date(2025, 2, 1)
        for key, expected in (
            ("start", "2025-01-01T06:00:00+00:00"),
            ("end", "2025-02-01T07:00:00+00:00"),
        ):
            if key in manifest and manifest[key] != expected:
                return None
    elif contract == "den-ghcnh-aviation-independent-60m-v2":
        station, earliest, latest = "USW00003017", dt.date(2023, 1, 1), dt.date(2026, 1, 1)
        if "scope_start" not in manifest or "scope_end_exclusive" not in manifest:
            return None
    else:
        return None
    if manifest.get("station") != station:
        return None
    if "scope_start" not in manifest and "scope_end_exclusive" not in manifest:
        return WeatherCoverage(earliest, latest - dt.timedelta(days=1))
    try:
        start = dt.date.fromisoformat(manifest["scope_start"])
        end = dt.date.fromisoformat(manifest["scope_end_exclusive"])
        if (
            start.isoformat() != manifest["scope_start"]
            or end.isoformat() != manifest["scope_end_exclusive"]
        ):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    if not earliest <= start < end <= latest:
        return None
    return WeatherCoverage(start, end - dt.timedelta(days=1))


_DEFAULT_WEATHER_MANIFEST = object()


def weather_scope(filters, manifest=_DEFAULT_WEATHER_MANIFEST):
    # Retain the original one-argument January helper, not a production fallback.
    coverage = (
        WeatherCoverage(dt.date(2025, 1, 1), dt.date(2025, 1, 31))
        if manifest is _DEFAULT_WEATHER_MANIFEST
        else weather_coverage(manifest)
    )
    return bool(
        coverage
        and filters.origin == coverage.origin_id
        and coverage.start <= filters.start <= filters.end <= coverage.end
    )


def airport_label(airport_id, code, locations=None):
    city = (locations or {}).get((airport_id, code))
    return f"{city} ({code})" if city else code


def group_label(row, group, locations=None):
    if group == "carrier":
        return airline_label(row.get("MARKETING_CARRIER_ID"), row["MARKETING_LABEL"])
    if group == "airport":
        return airport_label(row.get("ORIGIN_ID"), row["ORIGIN_LABEL"], locations)
    if group == "route":
        origin = airport_label(row.get("ORIGIN_ID"), row["ORIGIN_LABEL"], locations)
        destination = airport_label(row.get("DESTINATION_ID"), row["DESTINATION_LABEL"], locations)
        return f"{origin} → {destination}"
    if group == "month":
        return str(row["MONTH_START"])[:7]
    if group == "weekday":
        return calendar.day_name[int(row["WEEKDAY"]) - 1]
    hour = int(row["SCHEDULED_LOCAL_HOUR"])
    return "Source 2400" if hour == 24 else f"{hour:02}:00"


@lru_cache(maxsize=1)
def _airline_names():
    return json.loads(files("airline_warehouse").joinpath("airline_names.json").read_text())[
        "airlines"
    ]


def airline_label(carrier_id, code):
    match = _airline_names().get(str(carrier_id))
    return f"{match['name']} ({code})" if match and match["code"] == code else code


def ordered_rows(rows, group):
    field = {"month": "MONTH_START", "weekday": "WEEKDAY", "hour": "SCHEDULED_LOCAL_HOUR"}.get(
        group
    )
    return sorted(rows, key=lambda r: r[field]) if field else list(rows)


def comparison_table(rows, group, locations=None):
    def rate(v):
        return None if v is None else float(v) * 100

    return [
        {
            "Group": group_label(r, group, locations),
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
