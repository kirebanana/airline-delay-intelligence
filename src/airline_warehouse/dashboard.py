"""Thin local-only aggregate presentation; no refresh or publication side effects."""

import json
import os
from pathlib import Path

import streamlit as st

from airline_warehouse.analytics import filter_options, query_metrics, relation
from airline_warehouse.connection import connect_as


@st.cache_data(ttl=900, max_entries=256, show_spinner=False)
def cached_metrics(identity, descriptor, filters, group, minimum, _reader):
    return _reader.metrics(descriptor, filters, group, minimum)


@st.cache_data(ttl=15, max_entries=16, show_spinner=False)
def cached_options(identity, descriptor, _reader):
    return _reader.options(descriptor)


class Reader:
    def __init__(self, connection, development_candidate: Path | None = None):
        self.connection = connection
        self.development_candidate = development_candidate

    def pin(self):
        if self.development_candidate is not None:
            descriptor = json.loads(self.development_candidate.read_text())
            relation(descriptor, development=True)
            return {**descriptor, "development": True, "target": "development"}
        raise ValueError(
            "Published read provider is not initialized; ticket07 bootstrap is pending"
        )

    def validate(self, descriptor):
        if not descriptor.get("development"):
            raise ValueError("No publication-qualified reader token is available yet")

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


def render(reader):
    import pandas as pd
    import streamlit as st

    from airline_warehouse.analytics import Filters, cache_identity
    from airline_warehouse.dashboard import cached_metrics, cached_options

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
        st.caption("Validated first-month release; not final 36-month project acceptance.")
    st.caption(
        f"Coverage: {options['start']} to {options['end']}; "
        "marketing-table source rows, not passengers."
    )
    st.caption(
        "Processed: "
        + str(descriptor.get("built_at"))
        + "; release: "
        + str(descriptor.get("release_id", "none (development)"))
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
                return str(row[field])

            chart = chart.copy()
            chart["Group"] = chart.apply(group_label, axis=1)
            st.bar_chart(chart.set_index("Group")[metric].astype(float))
            st.caption(
                "Rates shown on a 0–1 scale; chart membership uses metric-specific eligibility."
            )
    st.caption(
        "Local scheduled hours—not actual departure/UTC cohorts. A→B differs from B→A. "
        "Descriptive comparisons reflect carrier, route and schedule mix; "
        "no causality or fairness adjustment."
    )
    with st.expander("Methodology and data quality"):
        st.write(
            "Arrival eligibility excludes cancellations/diversions and unknown arrival indicators. "
            "Departure eligibility excludes cancellations but includes diversions "
            "with known indicators. Exactly 15 minutes is delayed. Rates use aggregate counts; "
            "quantiles use eligible values. Unknown cancellation/diversion flags block acceptance. "
            "Historical source codes/sequence IDs remain on facts; display labels describe "
            "the selected scope. Weather/categories/recovery are later tickets."
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
