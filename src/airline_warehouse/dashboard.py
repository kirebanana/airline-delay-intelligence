"""Thin local-only aggregate presentation; no refresh or publication side effects."""

import json
import os
from pathlib import Path

import streamlit as st

from airline_warehouse.analytics import (
    filter_options,
    query_metrics,
    query_secondary,
    query_weather,
    relation,
)
from airline_warehouse.connection import connect_as


@st.cache_data(ttl=900, max_entries=256, show_spinner=False)
def cached_metrics(identity, descriptor, filters, group, minimum, _reader):
    return _reader.metrics(descriptor, filters, group, minimum)


@st.cache_data(ttl=15, max_entries=16, show_spinner=False)
def cached_options(identity, descriptor, _reader):
    return _reader.options(descriptor)


@st.cache_data(ttl=900, max_entries=256, show_spinner=False)
def cached_secondary(identity, descriptor, filters, _reader):
    return _reader.secondary(descriptor, filters)


@st.cache_data(ttl=900, max_entries=128, show_spinner=False)
def cached_weather(identity, descriptor, filters, _reader):
    return _reader.weather(descriptor, filters)


class Reader:
    def __init__(self, connection, development_candidate: Path | None = None):
        self.connection = connection
        self.development_candidate = development_candidate

    def pin(self):
        if self.development_candidate is not None:
            descriptor = json.loads(self.development_candidate.read_text())
            relation(descriptor, development=True)
            return {**descriptor, "development": True, "target": "development"}
        from airline_warehouse.publication import active_release

        return active_release(self.connection, "january")

    def validate(self, descriptor):
        if not descriptor.get("development"):
            from airline_warehouse.publication import validate_reader_token

            validate_reader_token(self.connection, descriptor)

    def options(self, descriptor):
        return filter_options(
            self.connection, descriptor, development=descriptor.get("development", False)
        )

    def metrics(self, descriptor, filters, group, minimum):
        return query_metrics(
            self.connection,
            descriptor,
            filters,
            group,
            minimum=minimum,
            development=descriptor.get("development", False),
        )

    def secondary(self, descriptor, filters):
        return query_secondary(
            self.connection,
            descriptor,
            filters,
            development=descriptor.get("development", False),
        )

    def weather(self, descriptor, filters):
        return query_weather(
            self.connection, descriptor, filters, development=descriptor.get("development", False)
        )


def render(reader):
    import pandas as pd
    import streamlit as st

    from airline_warehouse.analytics import Filters, cache_identity
    from airline_warehouse.dashboard import (
        cached_metrics,
        cached_options,
        cached_secondary,
        cached_weather,
    )
    from airline_warehouse.warehouse import BASELINE_MONTHS

    st.title("Airline Delay Intelligence")
    try:
        descriptor = reader.pin()  # exactly one descriptor, reused throughout this render
        reader.validate(descriptor)
        options = cached_options(
            (
                "DC50202",
                descriptor.get("target"),
                descriptor["schema"],
                descriptor["processing_contract"],
            ),
            descriptor,
            reader,
        )
    except Exception:
        st.info(
            "Unavailable: no readable validated release. "
            "Complete bootstrap or explicitly select development mode."
        )
        st.stop()
    if descriptor.get("development"):
        st.warning("DEVELOPMENT — UNPUBLISHED. Not a validated immutable release.")
    else:
        complete = set(descriptor["inputs"]) == BASELINE_MONTHS
        st.caption(
            "Validated 2023–2025 baseline; cloud/platform final acceptance remains separate."
            if complete
            else f"Validated partial baseline ({len(descriptor['inputs'])} selected month(s)); "
            "not final 36-month project acceptance."
        )
    st.caption(
        f"Coverage: {options['start']} to {options['end']}; "
        "marketing-table source rows, not passengers."
    )
    st.caption(
        "Processed: "
        + str(descriptor.get("built_at"))
        + "; release: "
        + str(descriptor.get("release_id", "none (development)"))
        + "; published: "
        + str(descriptor.get("published_at", "not published"))
    )

    def reset():
        for key in ("dates", "carriers", "origin", "destination", "minimum", "group"):
            st.session_state.pop(key, None)

    with st.sidebar:
        st.button("Reset filters", key="reset", on_click=reset)
        dates = st.date_input(
            "Source dates",
            (options["start"], options["end"]),
            min_value=options["start"],
            max_value=options["end"],
            key="dates",
        )
        carriers = dict(options["carriers"])
        chosen = st.multiselect(
            "Marketing carrier (stable DOT ID)",
            list(carriers),
            key="carriers",
            format_func=lambda v: f"{carriers[v]} ({v})",
        )
        airports = dict(options["airports"])

        def label(v):
            return "All" if v is None else f"{airports[v]} ({v})"

        origin = st.selectbox("Origin", [None, *airports], format_func=label, key="origin")
        destination = st.selectbox(
            "Destination", [None, *airports], format_func=label, key="destination"
        )
        minimum = st.number_input(
            "Ranking minimum eligible observations",
            min_value=1,
            max_value=1_000_000,
            value=100,
            step=1,
            key="minimum",
        )
        group = st.selectbox(
            "Analysis", ["carrier", "month", "weekday", "hour", "airport", "route"], key="group"
        )
    if len(dates) != 2:
        st.info("Select both dates before querying.")
        st.stop()
    filters = Filters(dates[0], dates[1], tuple(chosen), origin, destination)
    st.caption(
        f"Applied: {dates[0]}–{dates[1]}; carriers {chosen or 'all'}; "
        f"ordered route {label(origin)} → {label(destination)}; minimum {minimum}."
    )
    try:
        reader.validate(descriptor)  # also checked before cache hits; no expired-token fallback
        summary = cached_metrics(
            cache_identity(descriptor, filters, "all", minimum, 500),
            descriptor,
            filters,
            "all",
            minimum,
            reader,
        )[0]
        reader.validate(descriptor)
        detail = cached_metrics(
            cache_identity(descriptor, filters, group, minimum, 500),
            descriptor,
            filters,
            group,
            minimum,
            reader,
        )
    except Exception:
        st.error(
            "Results unavailable or release token expired. "
            "Reload; no partial/new-release fallback was used."
        )
        st.stop()
    labels = [
        ("Arrival on-time", "ARRIVAL_RATE"),
        ("Cancellation", "CANCELLATION_RATE"),
        ("Diversion", "DIVERSION_RATE"),
        ("Departure delay ≥15 min", "DEPARTURE_RATE"),
    ]
    for col, (name, key) in zip(st.columns(4), labels, strict=True):
        value = summary[key]
        col.metric(name, "N/A" if value is None else f"{float(value) * 100:.1f}%")
    n = int(summary["SCHEDULED_ROWS"])
    st.write(f"Scheduled source rows: {n:,}")
    if not n:
        st.info(
            "No observations match these filters. Zero denominators are N/A, not zero performance."
        )
    counts = []
    for measure, num, den, unknown in (
        ("Arrival on-time", "ARRIVAL_NUMERATOR", "ARRIVAL_DENOMINATOR", "UNKNOWN_ARRIVAL"),
        ("Cancellation", "CANCELLATION_NUMERATOR", "SCHEDULED_ROWS", "UNKNOWN_CANCELLED"),
        ("Diversion", "DIVERSION_NUMERATOR", "SCHEDULED_ROWS", "UNKNOWN_DIVERTED"),
        ("Departure delay", "DEPARTURE_NUMERATOR", "DEPARTURE_DENOMINATOR", "UNKNOWN_DEPARTURE"),
    ):
        counts.append(
            {
                "Measure": measure,
                "Numerator": summary[num],
                "Eligible denominator": summary[den],
                "Excluded": n - int(summary[den]),
                "Unknown indicator/flag": summary[unknown],
            }
        )
    st.dataframe(counts, hide_index=True)
    st.write("Signed ordinary-arrival delay (minutes); early arrivals remain negative.")
    for col, (name, key) in zip(
        st.columns(3),
        [("Mean", "SIGNED_MEAN"), ("Median", "SIGNED_MEDIAN"), ("Exact p90", "SIGNED_P90")],
        strict=True,
    ):
        col.metric(name, "N/A" if summary[key] is None else f"{float(summary[key]):.1f}")
    st.caption(
        f"Signed-delay eligible count: {summary['SIGNED_ARRIVAL_COUNT']}; "
        "may differ from indicator eligibility."
    )
    if detail:
        frame = pd.DataFrame(detail)
        st.dataframe(frame, hide_index=True)
        st.caption(
            "Up to 500 groups, ordered by volume—not a performance ranking. "
            "Narrow filters for sparse groups."
        )
        metric = "DEPARTURE_RATE" if group == "airport" else "ARRIVAL_RATE"
        eligible = "DEPARTURE_RANKABLE" if group == "airport" else "ARRIVAL_RANKABLE"
        chart = frame[frame[eligible].fillna(False)]
        suppressed = len(frame) - len(chart)
        if suppressed:
            st.warning(
                f"{suppressed} groups are below this metric's eligible-count threshold. "
                "They remain in detail but are excluded from the comparison chart."
            )
        if chart.empty:
            st.warning(
                "No groups meet this metric's ranking threshold; detail remains inspectable."
            )
        else:

            def group_label(row):
                if group == "carrier":
                    return f"{row['MARKETING_LABEL']} ({row['MARKETING_CARRIER_ID']})"
                if group == "airport":
                    return f"{row['ORIGIN_LABEL']} ({row['ORIGIN_ID']})"
                if group == "route":
                    return (
                        f"{row['ORIGIN_LABEL']} ({row['ORIGIN_ID']}) → "
                        f"{row['DESTINATION_LABEL']} ({row['DESTINATION_ID']})"
                    )
                field = {
                    "month": "MONTH_START",
                    "weekday": "WEEKDAY",
                    "hour": "SCHEDULED_LOCAL_HOUR",
                }[group]
                if group == "hour" and row[field] == 24:
                    return "Source 2400 midnight (date not inferred)"
                return str(row[field])

            chart = chart.copy()
            chart["Group"] = chart.apply(group_label, axis=1)
            st.bar_chart(chart.set_index("Group")[metric].astype(float))
            st.caption(
                "Rates shown on a 0–1 scale; chart membership uses metric-specific eligibility."
            )
    st.caption(
        "Local scheduled hours—not actual departure/UTC cohorts. A→B differs from B→A. "
        "Source clock 2400 is a separate midnight bucket, "
        "not a 24th hour or a next-day conversion; "
        "source reporting dates stay unchanged. "
        "Descriptive comparisons reflect carrier, route and schedule mix; "
        "no causality or fairness adjustment."
    )
    st.subheader("DEN investigation — scheduled weather context")
    if descriptor.get("weather"):
        try:
            reader.validate(descriptor)
            weather = cached_weather(
                cache_identity(descriptor, filters, "all", minimum, 500),
                descriptor,
                filters,
                reader,
            )
        except Exception:
            st.error("Weather results unavailable. Reload; no partial-release fallback was used.")
            st.stop()
        st.caption(
            "Fixed DEN-origin, Denver-local January 2025 only, including cancellations/diversions. "
            "Latest independently accepted observation at/before scheduled departure, age ≤60 min. "
            "Temperature °C; wind m/s; visibility m. Each variable may use a different time."
        )
        st.write(
            "Complete pilot coverage — all scheduled pilot rows, unaffected by sidebar filters"
        )
        st.dataframe(weather["pilot_coverage"], hide_index=True)
        st.write(
            "Filtered DEN context — sidebar dates, carrier and directional-route filters apply"
        )
        st.dataframe(weather["selected_coverage"], hide_index=True)
        comparisons = weather["comparisons"]
        if comparisons:
            st.dataframe(comparisons, hide_index=True)
            if any(r["LOCAL_DATES"] < 5 or r["SCHEDULED_ROWS"] < minimum for r in comparisons):
                st.warning(
                    "Some weather groups have fewer than five local dates or the eligible-count "
                    "threshold. Inspect support; they are not performance rankings."
                )
        else:
            st.info("No DEN pilot rows match these filters; national weather is not available.")
        with st.expander("Weather daily coverage and episode concentration"):
            st.dataframe(weather["daily"], hide_index=True)
        st.caption(
            "Largest-date share shows episode concentration: flights on a shared date/episode "
            "are not independent weather events. Unmatched rows remain visible, not benign. "
            "Carrier/route/hour mix and cancellation selection confound comparisons. "
            "Scheduled conditions do not establish conditions at a cancellation decision, "
            "real-time availability, or that weather caused disruption. No compound conditions."
        )
    else:
        st.info("This release does not yet contain the qualified DEN/local-January weather pilot.")
    # Old descriptors remain readable but do not pretend to contain new model fields.
    if descriptor.get("analytical_contract") == "secondary-v1" or descriptor.get("development"):
        try:
            reader.validate(descriptor)
            secondary = cached_secondary(
                cache_identity(descriptor, filters, "all", minimum, 500),
                descriptor,
                filters,
                reader,
            )
        except Exception:
            st.error("Secondary results unavailable. Reload; no release fallback was used.")
            st.stop()
        s = secondary["summary"]
        st.subheader("Reported delay categories")
        st.write(
            f"Late ordinary arrivals: {s['CATEGORY_ELIGIBLE']}; complete five-category subset: "
            f"{s['CATEGORY_COMPLETE']}; missing allocations: {s['MISSING_CATEGORY_ROWS']}. "
            "Cancelled/diverted rows and unknown arrival indicators are excluded."
        )
        st.write(
            "Excluded arrival-delay minutes on incomplete allocation rows: "
            + (
                "N/A (no known minutes)"
                if s["EXCLUDED_ARRIVAL_MINUTES"] is None
                else str(s["EXCLUDED_ARRIVAL_MINUTES"])
            )
            + f"; complete-subset allocation mismatches: {s['ALLOCATION_MISMATCH_ROWS']}."
        )
        if 0 < int(s["CATEGORY_COMPLETE"]) < minimum:
            st.warning(
                "Category subset is below the displayed sample-size threshold; inspect with care."
            )
        st.caption(
            "Minute share = category minutes / all reported category minutes on the complete "
            "late-arrival subset—not a share of all arrival-delay minutes. Affected rate = "
            "positive allocations / complete late arrivals. Categories overlap; rates need not "
            "sum to 100%. These are reported attributions, not proven causes; Weather is not "
            "every weather-associated disruption."
        )
        if s["UNALLOCATED_MINUTES"]:
            st.warning(f"Unallocated arrival-delay minutes: {s['UNALLOCATED_MINUTES']}; preserved.")
        st.dataframe(secondary["categories"], hide_index=True)
        st.write(
            "Cancellation reasons — counts and shares of cancelled rows only; unknowns retained."
        )
        st.dataframe(secondary["cancellations"], hide_index=True)
        st.subheader("Schedule-relative recovery")
        if 0 < int(s["RECOVERY_ELIGIBLE"]) < minimum:
            st.warning(
                "Recovery subset is below the displayed sample-size threshold; inspect with care."
            )
        st.write(
            f"Eligible late departures: {s['RECOVERY_ELIGIBLE']}; "
            f"excluded scheduled rows: {int(s['SCHEDULED_ROWS']) - int(s['RECOVERY_ELIGIBLE'])}; "
            f"arrived below 15 minutes late: {s['RECOVERED']}."
        )
        value = s["RECOVERY_SHARE"]
        st.metric(
            "Recovered below 15 minutes / eligible late departures",
            "N/A" if value is None else f"{float(value):.1%}",
        )
        for col, (label, field) in zip(
            st.columns(3),
            (
                ("Mean improvement", "IMPROVEMENT_MEAN"),
                ("Median improvement", "IMPROVEMENT_MEDIAN"),
                ("Exact p90 improvement", "IMPROVEMENT_P90"),
            ),
            strict=True,
        ):
            value = s[field]
            col.metric(label, "N/A" if value is None else f"{float(value):.1f} min")
        st.dataframe(secondary["distribution"], hide_index=True)
        st.caption(
            "Ordinary noncancelled/nondiverted completions departing ≥15 minutes late, "
            "with both signed delays known. Improvement = departure delay − arrival delay; "
            "zero/negative values remain. Positive improvement is not proof of faster flying "
            "or a causal intervention."
        )
    with st.expander("Methodology and data quality"):
        st.write(
            "Arrival eligibility excludes cancellations/diversions and unknown arrival indicators. "
            "Departure eligibility excludes cancellations but includes diversions "
            "with known indicators. Exactly 15 minutes is delayed. Rates use aggregate counts; "
            "quantiles use eligible values. Unknown cancellation/diversion flags block acceptance. "
            "Historical source codes/sequence IDs remain on facts; display labels describe "
            "the selected scope. Weather is a fixed DEN/local-January pilot, not national context."
        )


def main():
    st.set_page_config(page_title="Airline Delay Intelligence", layout="wide")
    try:
        path = os.environ.get("AIRLINE_DEVELOPMENT_CANDIDATE")
        with connect_as("reader") as connection:
            render(Reader(connection, Path(path) if path else None))
    except Exception:
        st.error(
            "Reader connection unavailable. Check protected identity/bootstrap; "
            "no privileged fallback."
        )
