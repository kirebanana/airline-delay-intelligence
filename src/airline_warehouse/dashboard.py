"""Local release-pinned analytics. No refresh/publication side effects."""

import datetime as dt
import json
import os
from dataclasses import replace
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from airline_warehouse.analytics import (
    Filters,
    cache_identity,
    filter_options,
    query_metrics,
    query_secondary,
    query_weather,
    relation,
)
from airline_warehouse.connection import connect_as
from airline_warehouse.dashboard_views import (
    RATES,
    RECOVERY_ORDER,
    TASKS,
    WEATHER_BANDS,
    arrival_timing,
    comparison_table,
    group_label,
    number,
    ordered_rows,
    percent,
    percent_value,
    prior_year,
    sort_comparisons,
    weather_scope,
    weather_support,
)


@st.cache_data(ttl=900, max_entries=256, show_spinner=False)
def cached_metrics(identity, descriptor, filters, group, minimum, _reader):
    return _reader.metrics(descriptor, filters, group, minimum)


@st.cache_data(ttl=900, max_entries=16, show_spinner=False)
def cached_options(identity, descriptor, _reader):
    return _reader.options(descriptor)


@st.cache_data(ttl=900, max_entries=256, show_spinner=False)
def cached_secondary(identity, descriptor, filters, _reader):
    return _reader.secondary(descriptor, filters)


@st.cache_data(ttl=900, max_entries=128, show_spinner=False)
def cached_weather(identity, descriptor, filters, details, _reader):
    return _reader.weather(descriptor, filters, details=details)


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
            self.connection, descriptor, filters, development=descriptor.get("development", False)
        )

    def weather(self, descriptor, filters, *, details=True):
        return query_weather(
            self.connection,
            descriptor,
            filters,
            development=descriptor.get("development", False),
            details=details,
        )


def table(rows):
    if rows:
        labels = {
            "Scheduled": "Flights",
            "p90 min": "90% delay (min)",
            "Median min": "Typical delay (min)",
            "Arrival eligible": "With arrival data",
            "Departure eligible": "With departure data",
            "Signed eligible": "With delay data",
            "Current eligible": "Flights this period",
            "Prior eligible": "Flights last year",
            "Eligible": "Flights used",
            "Excluded": "Not used",
            "Largest date": "Busiest day's share",
            "Change (pp)": "Change (points)",
        }
        configs = {}
        for key in rows[0]:
            if any(isinstance(r.get(key), str) for r in rows):
                continue
            if key in (
                "On-time",
                "Cancelled",
                "Diverted",
                "Departure delayed",
                "Minute share",
                "Affected flights",
                "Share",
                "Coverage",
                "Largest date",
                "Current",
                "Prior year",
            ):
                configs[key] = st.column_config.NumberColumn(label=labels.get(key), format="%.1f%%")
            elif key in (
                "Scheduled",
                "Arrival eligible",
                "Departure eligible",
                "Signed eligible",
                "Reported minutes",
                "Cancelled rows",
                "Flights",
                "Matched",
                "Unmatched",
                "Current eligible",
                "Prior eligible",
                "Eligible",
                "Excluded",
            ):
                configs[key] = st.column_config.NumberColumn(label=labels.get(key), format="%,d")
            elif key in ("Median min", "p90 min"):
                configs[key] = st.column_config.NumberColumn(
                    label=labels.get(key),
                    format="%.1f",
                    help="90% of arrivals had no more delay than this. Early arrivals are negative."
                    if key == "p90 min"
                    else "The middle arrival delay. Early arrivals are negative.",
                )
            elif key == "Change (pp)":
                configs[key] = st.column_config.NumberColumn(label=labels.get(key), format="%.2f")
        st.dataframe(rows, hide_index=True, width="stretch", column_config=configs)
    else:
        st.info("No flights match these filters. N/A means no result, not 0%.")


def plot(rows, label, value, *, order=None, horizontal=True, rate=False):
    if not rows or not any(r.get(value) is not None for r in rows):
        st.info("Not enough flight data to draw this chart.")
        return
    frame = pd.DataFrame(rows)
    frame[value] = pd.to_numeric(frame[value], errors="coerce")
    category = alt.X if not horizontal else alt.Y
    measure = alt.Y if not horizontal else alt.X
    chart = (
        alt.Chart(frame)
        .mark_bar(color="#167D8D")
        .encode(
            **{
                "y" if horizontal else "x": category(
                    f"{label}:N",
                    sort=order or list(frame[label]),
                    title=None,
                    axis=alt.Axis(labelOverlap=False, labelLimit=240) if horizontal else alt.Axis(),
                ),
                "x" if horizontal else "y": measure(
                    f"{value}:Q", title=value, axis=alt.Axis(format=".1%" if rate else "~s")
                ),
            },
            tooltip=[
                alt.Tooltip(f"{label}:N"),
                alt.Tooltip(f"{value}:Q", format=".1%" if rate else ",.1f"),
            ],
        )
        .properties(height=max(180, len(rows) * 32) if horizontal else 270)
        .configure_axis(labelColor="#334155", titleColor="#16354A", labelFontSize=12)
        .configure_legend(labelColor="#334155", titleColor="#16354A")
    )
    st.altair_chart(chart, width="stretch")


def comparison(rows, group, summary, minimum):
    st.subheader(
        "Compare "
        + {
            "carrier": "airlines",
            "airport": "departure airports",
            "route": "routes",
            "month": "months",
            "weekday": "days of the week",
            "hour": "departure hours",
        }.get(group, group)
    )
    metric = st.selectbox(
        "Comparison metric",
        list(RATES),
        key=f"metric_{group}",
        index=3 if group == "airport" else 0,
    )
    field, denominator = RATES[metric]
    temporal = group in ("month", "weekday", "hour")
    ordered = ordered_rows(rows, group)
    eligible = [r for r in ordered if r[denominator] >= minimum]
    if group == "carrier" or temporal:
        selected = ordered
    else:
        count = st.slider(
            "Busiest routes to show" if group == "route" else "Busiest airports to show",
            5,
            30,
            10,
            key=f"top_{group}",
        )
        selected = eligible[:count]
    if not temporal:
        order = st.selectbox(
            "Order by",
            ["Highest rate first", "Lowest rate first", "Most flights", "Name (A–Z)"],
            index=0 if field == "ARRIVAL_RATE" else 1,
            key=f"order_{group}",
        )
        selected = sort_comparisons(selected, group, field, denominator, minimum, order)
        shown = sum(int(r["SCHEDULED_ROWS"]) for r in selected)
        total = int(summary["SCHEDULED_ROWS"])
        if group == "carrier":
            st.caption(
                f"All {len(selected)} airlines with flights in your selection. "
                "Use Order by to change the chart and table order."
            )
        elif total:
            st.caption(
                f"{len(selected)} busiest {'routes' if group == 'route' else 'airports'} "
                f"· {shown / total:.1%} of flights in your selection. "
                "Ordering applies to this set, not the whole network."
            )
        if group in ("route", "airport"):
            with st.expander("Which flights does this comparison cover?"):
                st.write(
                    "The chart starts with the busiest routes or airports, then orders "
                    "that set by your chosen measure. Up to 500 are available in the "
                    "full table. This is not a ranking of every route or airport."
                )
    if len(rows) != len(eligible):
        st.caption(
            f"{len(rows) - len(eligible)} groups have fewer than {minimum:,} flights "
            "with the data needed for this measure; their chart values are left blank."
        )
    plot(
        [
            {
                "Group": group_label(r, group),
                metric: r[field] if r[denominator] >= minimum else None,
            }
            for r in selected
        ],
        "Group",
        metric,
        horizontal=not temporal,
        rate=True,
    )
    compact = comparison_table(selected, group)
    # Deliberate primary columns: trade-offs together, support and quantiles nearby.
    primary = ["Group", "On-time", "Cancelled", "Diverted", "Scheduled", "p90 min"]
    if group == "airport":
        metric_column = {
            "Arrival on-time": "On-time",
            "Cancellation": "Cancelled",
            "Diversion": "Diverted",
            "Departure delay ≥15 min": "Departure delayed",
        }[metric]
        support_column = {
            "ARRIVAL_DENOMINATOR": "Arrival eligible",
            "SCHEDULED_ROWS": "Scheduled",
            "DEPARTURE_DENOMINATOR": "Departure eligible",
        }[denominator]
        primary = list(
            dict.fromkeys(
                ["Group", metric_column, support_column, "Cancelled", "Scheduled", "p90 min"]
            )
        )
    table([{k: r[k] for k in primary} for r in compact])
    with st.expander("Full comparison table and flight counts"):
        table(comparison_table(rows, group))
        st.caption(
            "On-time arrival excludes cancelled and diverted flights. Delay figures keep "
            "early arrivals negative. Carriers serve different routes and schedules, "
            "so these comparisons do not isolate the effect of the carrier itself."
        )


def disruption(data, minimum):
    s = data["summary"]
    st.subheader("What types of delay were reported?")
    st.write(
        f"Complete category data for {number(s['CATEGORY_COMPLETE'])} of "
        f"{number(s['CATEGORY_ELIGIBLE'])} late arrivals. "
        f"Missing category data: {number(s['MISSING_CATEGORY_ROWS'])} flights."
    )
    categories = [
        {
            "Category": "National Airspace System (NAS)"
            if r["CATEGORY"] == "NAS"
            else r["CATEGORY"],
            "Minute share": r["MINUTE_SHARE"],
            "Minutes": r["REPORTED_MINUTES"],
            "Affected": r["AFFECTED_RATE"],
        }
        for r in data["categories"]
    ]
    categories.sort(key=lambda r: float(r["Minute share"] or 0), reverse=True)
    plot(categories, "Category", "Minute share", rate=True)
    table(
        [
            {
                "Category": r["Category"],
                "Reported minutes": r["Minutes"],
                "Minute share": percent_value(r["Minute share"]),
                "Affected flights": percent_value(r["Affected"]),
            }
            for r in categories
        ]
    )
    st.caption(
        "The chart divides reported delay minutes by category. A flight can have more than "
        "one category, so the percentages of flights affected can add up to more than 100%. "
        "These are reported explanations, not proof of cause."
    )
    with st.expander("How delay categories are counted"):
        st.write(
            "Delay minutes on flights missing category data (not in the chart): "
            f"{number(s['EXCLUDED_ARRIVAL_MINUTES'])}; "
            f"flights whose category minutes do not match total delay: "
            f"{number(s['ALLOCATION_MISMATCH_ROWS'])}."
        )
        st.write(
            "Only arrivals at least 15 minutes late, with all five categories reported, "
            "are included. Cancelled/diverted flights and unknown arrival status are excluded."
        )
        st.write(
            f"Delay minutes not assigned to a category: {number(s['UNALLOCATED_MINUTES'])}. "
            "Original reported values are kept; no missing values are filled in."
        )
    st.subheader("Cancellation reasons")
    st.caption(
        "These percentages describe cancelled flights, not delay minutes. "
        "Weather-related cancellations are separate from the weather delay category above."
    )
    reasons = [
        {
            "Reason": r["CANCELLATION_REASON"].replace("NAS", "National Airspace System (NAS)"),
            "Cancelled rows": r["CANCELLED_ROWS"],
            "Share": percent_value(r["CANCELLED_SHARE"]),
        }
        for r in data["cancellations"]
    ]
    table(reasons)
    st.subheader("Did flights make up time after a late departure?")
    st.metric(
        "Late departures that arrived less than 15 minutes late", percent(s["RECOVERY_SHARE"])
    )
    st.write(
        f"{number(s['RECOVERED'])} of {number(s['RECOVERY_ELIGIBLE'])} late departures "
        "arrived less than 15 minutes late."
    )
    st.write(
        "Minutes made up between departure and arrival: "
        f"average {number(s['IMPROVEMENT_MEAN'], ' min', 1)}, "
        f"typical (median) {number(s['IMPROVEMENT_MEDIAN'], ' min', 1)}."
    )
    bands = sorted(data["distribution"], key=lambda r: RECOVERY_ORDER.index(r["RECOVERY_BAND"]))
    distribution = [
        {
            "Improvement band": {
                "Worsened (<0)": "Arrived more late",
                "Unchanged (0)": "No time made up",
                "Improved (0–<15)": "Made up under 15 min",
                "Improved (15–<30)": "Made up 15 to under 30 min",
                "Improved (≥30)": "Made up 30+ min",
            }[r["RECOVERY_BAND"]],
            "Share": float(r["ELIGIBLE_ROWS"]) / s["RECOVERY_ELIGIBLE"]
            if s["RECOVERY_ELIGIBLE"]
            else None,
            "Flights": r["ELIGIBLE_ROWS"],
        }
        for r in bands
    ]
    plot(distribution, "Improvement band", "Share", rate=True)
    table([{**r, "Share": percent_value(r["Share"])} for r in distribution])
    st.caption(
        "Positive values mean the arrival was less late than the departure; negative values "
        "mean it was more late. Making up some time does not necessarily mean arriving on time."
    )
    with st.expander("How making up time is measured"):
        st.write(
            "Flights must depart at least 15 minutes late, reach their planned destination "
            "and have both departure and arrival delay data. Minutes made up equals "
            "departure delay minus arrival delay. This does not prove faster flying."
        )
        st.write(f"90th percentile of minutes made up: {number(s['IMPROVEMENT_P90'], ' min', 1)}.")
        st.write(
            "Late departures missing arrival delay data: "
            f"{number(s.get('RECOVERY_MISSING_ARRIVAL'))}. "
            "Completed flights missing departure delay data: "
            f"{number(s.get('RECOVERY_MISSING_DEPARTURE'))}. "
            "Flights that did not depart late are outside this comparison."
        )
    if 0 < s["CATEGORY_COMPLETE"] < minimum or 0 < s["RECOVERY_ELIGIBLE"] < minimum:
        st.warning("One of these comparisons is based on fewer flights than your selected minimum.")


def weather_view(data, minimum):
    st.caption(
        "Weather near each flight's scheduled departure from Denver, January 2025. "
        "Observations are no more than one hour old; cancellations and diversions are included."
    )
    variable = st.selectbox(
        "Weather variable",
        ["temperature", "wind", "visibility"],
        format_func=lambda x: {
            "temperature": "Temperature (°C)",
            "wind": "Wind (m/s)",
            "visibility": "Visibility (m)",
        }[x],
    )
    rows = [r for r in data["comparisons"] if r["VARIABLE"] == variable]
    bands = WEATHER_BANDS[variable]
    rows.sort(key=lambda r: bands.index(r["BAND"]) if r["BAND"] in bands else len(bands))
    if not rows:
        st.info("No Denver weather-study flights match these filters.")
    display = []
    for r in rows:
        dates, schedules, departures = weather_support(r, minimum)
        display.append(
            {
                "Band": r["BAND"],
                "Departure delayed": percent_value(r["DEPARTURE_DELAY_RATE"]),
                "Cancelled": percent_value(r["CANCELLATION_RATE"]),
                "Scheduled": r["SCHEDULED_ROWS"],
                "Departure eligible": r["DEPARTURE_DENOMINATOR"],
                "Dates": r["LOCAL_DATES"],
                "Largest date": percent_value(r["LARGEST_DATE_SHARE"]),
                "Support": "Limited data"
                if not all((dates, schedules, departures))
                else "Enough flights/dates",
            }
        )
    table(display)
    if any(not all(weather_support(r, minimum)) for r in rows):
        st.warning(
            f"Some conditions have fewer than five days of data or fewer than {minimum:,} "
            "flights with the needed information. Treat these comparisons with extra care."
        )
    st.caption(
        "Check the number of days and the busiest day's share: many flights may come from "
        "a single weather event. Different airlines, routes and schedules also affect results. "
        "These comparisons do not prove weather caused a delay or cancellation."
    )
    st.subheader("How many flights have weather data?")
    coverage = [r for r in data["selected_coverage"] if r["VARIABLE"] == variable]
    table(
        [
            {
                "Flight status": "Cancelled" if r["CANCELLED"] else "Not cancelled",
                "Scheduled": r["SCHEDULED_ROWS"],
                "Matched": r["MATCHED_ROWS"],
                "Coverage": percent_value(r["COVERAGE"]),
                "Unmatched": r["SCHEDULED_ROWS"] - r["MATCHED_ROWS"],
            }
            for r in coverage
        ]
    )
    if data["pilot_coverage"]:
        with st.expander("Weather data for the whole Denver study"):
            table(data["pilot_coverage"])
        with st.expander("Daily weather coverage and missing data"):
            table([r for r in data["daily"] if r["VARIABLE"] == variable])
            table(coverage)


def render(reader):
    st.markdown(
        """<style>
    [data-testid="stMetricValue"] {font-size:1.8rem; white-space:normal; overflow:visible}
    [data-testid="stMetricLabel"] p {white-space:normal; overflow:visible}
    [data-testid="stCaptionContainer"] {opacity:1; color:#475569}
    [data-testid="stCaptionContainer"] p {color:#475569; font-size:0.9rem}
    @media (max-width:1100px) { [data-testid="stHorizontalBlock"] {flex-wrap:wrap}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]
      {min-width:210px; flex:1 1 210px} }
    </style>""",
        unsafe_allow_html=True,
    )
    st.title("Airline Delay Intelligence")
    st.caption("Explore airline reliability, delays and cancellations · US flights, 2023–2025")
    try:
        descriptor = reader.pin()
        reader.validate(descriptor)
        options = cached_options(
            (
                descriptor.get("target"),
                descriptor["schema"],
                descriptor["processing_contract"],
                descriptor.get("release_id"),
            ),
            descriptor,
            reader,
        )
    except Exception:
        st.error("Flight data is unavailable. Please reload or try again later.")
        st.stop()
    if descriptor.get("development"):
        st.warning("DEVELOPMENT — UNPUBLISHED. Not a validated immutable release.")
    defaults = {
        "dates": (options["start"], options["end"]),
        "carriers": [],
        "origin": None,
        "destination": None,
        "minimum": 100,
        "period": "All years",
        "group": "month",
    }

    def reset():
        for key, value in defaults.items():
            st.session_state[key] = value

    def period_change():
        p = st.session_state.period
        if p == "All years":
            st.session_state.dates = defaults["dates"]
        elif p != "Custom":
            if "-" in p:
                import calendar

                year, month = map(int, p.split("-"))
                st.session_state.dates = (
                    max(options["start"], dt.date(year, month, 1)),
                    min(options["end"], dt.date(year, month, calendar.monthrange(year, month)[1])),
                )
                return
            year = int(p)
            st.session_state.dates = (
                max(options["start"], dt.date(year, 1, 1)),
                min(options["end"], dt.date(year, 12, 31)),
            )

    def swap():
        st.session_state.origin, st.session_state.destination = (
            st.session_state.destination,
            st.session_state.origin,
        )

    def pilot():
        st.session_state.dates = (dt.date(2025, 1, 1), dt.date(2025, 1, 31))
        st.session_state.origin = 11292
        st.session_state.destination = None
        st.session_state.carriers = []
        st.session_state.period = "2025-01"

    def custom_dates():
        st.session_state.period = "Custom"

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    carriers, airports = dict(options["carriers"]), dict(options["airports"])

    def label(v):
        return "All" if v is None else airports[v]

    with st.sidebar:
        task = st.radio("Investigation", TASKS, key="task")
        st.button("Reset filters", key="reset", on_click=reset)
        st.selectbox(
            "Choose a year or month",
            [
                "All years",
                "Custom",
                *[str(y) for y in range(options["start"].year, options["end"].year + 1)],
                *[str(d)[:7] for d in pd.date_range(options["start"], options["end"], freq="MS")],
            ],
            key="period",
            on_change=period_change,
        )
        dates = st.date_input(
            "Source dates",
            min_value=options["start"],
            max_value=options["end"],
            key="dates",
            on_change=custom_dates,
        )
        chosen = st.multiselect(
            "Airline",
            list(carriers),
            key="carriers",
            format_func=lambda v: carriers[v],
            help="Marketing airline: the airline under whose code the flight was sold.",
        )
        origin = st.selectbox(
            "Origin", [None, *airports], format_func=label, key="origin", placeholder="All origins"
        )
        destination = st.selectbox(
            "Destination",
            [None, *airports],
            format_func=label,
            key="destination",
            placeholder="All destinations",
        )
        st.button("Reverse route", on_click=swap, disabled=origin is None or destination is None)
        minimum = st.number_input(
            "Minimum flights for comparisons",
            min_value=1,
            max_value=1_000_000,
            step=1,
            key="minimum",
            help="Groups below this flight count stay in the table but have no chart value. "
            "The count uses flights with the data needed for the selected measure.",
        )
        if task == TASKS[3]:
            st.button("Use DEN · January 2025", on_click=pilot)
        st.caption(
            "Filters update the results immediately. Choose a preset or enter your own dates."
        )
    if len(dates) != 2:
        st.info("Select both dates before querying.")
        st.stop()
    filters = Filters(dates[0], dates[1], tuple(chosen), origin, destination)
    st.header(task)
    st.caption(
        f"Applied: {dates[0]}–{dates[1]} · "
        f"{', '.join(carriers[c] for c in chosen) or 'All airlines'} · "
        f"{label(origin)} → {label(destination)}"
    )
    if task == TASKS[3]:
        st.info(
            "Weather is available for Denver departures in January 2025. "
            "You can narrow this to an airline, destination or dates within that month."
        )
        if not weather_scope(filters):
            st.warning(
                "Your current filters are outside this weather study. "
                "Select Denver in January 2025 to see matching flight and weather results."
            )
            st.button("Align filters to DEN · January 2025", on_click=pilot, type="primary")
            st.stop()

    def metrics(f=filters, group="all"):
        reader.validate(descriptor)  # validate even before cache hits; same pinned release
        return cached_metrics(
            cache_identity(descriptor, f, group, minimum, 500),
            descriptor,
            f,
            group,
            minimum,
            reader,
        )

    try:
        summary = metrics()[0]
        for col, (name, (field, denominator)) in zip(st.columns(4), RATES.items(), strict=True):
            col.metric(
                name,
                percent(summary[field]),
                help={
                    "ARRIVAL_RATE": "Arrived less than 15 minutes late. Excludes cancelled "
                    "and diverted flights and unknown arrival status.",
                    "CANCELLATION_RATE": "The percentage of scheduled flights that were cancelled.",
                    "DIVERSION_RATE": "Diverted flights as a percentage of all scheduled flights.",
                    "DEPARTURE_RATE": "Departed at least 15 minutes late. Excludes cancellations "
                    "and unknown departure status; includes flights later diverted.",
                }[field]
                + f" Based on {number(summary[denominator])} flights.",
                border=True,
            )
        st.write(f"**{number(summary['SCHEDULED_ROWS'])} scheduled flights** in your selection")
        if not summary["SCHEDULED_ROWS"]:
            st.info("No flights match these filters. N/A means no result, not 0%.")
        if task == TASKS[0]:
            comparison(metrics(group="carrier"), "carrier", summary, minimum)
            st.subheader("How performance changed each month")
            monthly = metrics(group="month")
            metric = st.selectbox("Trend metric", list(RATES), key="network_trend")
            field, den = RATES[metric]
            plot(
                [
                    {
                        "Month": group_label(r, "month"),
                        metric: r[field] if r[den] >= minimum else None,
                    }
                    for r in ordered_rows(monthly, "month")
                ],
                "Month",
                metric,
                horizontal=False,
                rate=True,
            )
            st.caption(
                f"Each bar shows the month's {metric.lower()} percentage. "
                "Months without enough flight data are left blank."
            )
        elif task == TASKS[1]:
            group = st.selectbox(
                "Explore by",
                ["month", "weekday", "hour", "route", "airport"],
                key="group",
                format_func=lambda g: {
                    "month": "Month",
                    "weekday": "Day of week",
                    "hour": "Departure hour",
                    "route": "Route",
                    "airport": "Departure airport",
                }[g],
            )
            comparison(metrics(group=group), group, summary, minimum)
            st.caption(
                "Departure hours use the scheduled local time. Source 2400 is shown "
                "separately because its date is not inferred. Routes are directional."
            )
            if origin is not None and destination is not None:
                st.subheader("Both route directions · same period & carriers")
                reverse = metrics(replace(filters, origin=destination, destination=origin))[0]
                table(
                    comparison_table(
                        [
                            {
                                **summary,
                                "ORIGIN_LABEL": label(origin),
                                "DESTINATION_LABEL": label(destination),
                            },
                            {
                                **reverse,
                                "ORIGIN_LABEL": label(destination),
                                "DESTINATION_LABEL": label(origin),
                            },
                        ],
                        "route",
                    )
                )
            previous = prior_year(filters, options["start"], options["end"])
            compare = st.checkbox(
                "Compare with same calendar dates last year", disabled=previous is None
            )
            if compare and previous is not None:
                reference = metrics(previous)[0]
                st.subheader("Compared with the same period last year")
                st.caption(
                    f"{filters.start}–{filters.end} versus {previous.start}–{previous.end}, "
                    "with the same airline and route filters. February 29 maps to February 28. "
                    "Route and schedule differences between years can affect the comparison."
                )
                table(
                    [
                        {
                            "Measure": name,
                            "Current": percent_value(summary[field]),
                            "Prior year": percent_value(reference[field]),
                            "Change (pp)": (float(summary[field]) - float(reference[field])) * 100
                            if summary[field] is not None and reference[field] is not None
                            else None,
                            "Current eligible": summary[den],
                            "Prior eligible": reference[den],
                        }
                        for name, (field, den) in RATES.items()
                    ]
                )
            if previous is None:
                st.caption(
                    "Choose dates in 2024 or 2025 to compare with the same period last year."
                )
        elif task == TASKS[2]:
            if descriptor.get("analytical_contract") == "secondary-v1" or descriptor.get(
                "development"
            ):
                reader.validate(descriptor)
                disruption(
                    cached_secondary(
                        cache_identity(descriptor, filters, "all", 1, 500),
                        descriptor,
                        filters,
                        reader,
                    ),
                    minimum,
                )
            else:
                st.info("This release does not contain secondary analyses.")
        elif descriptor.get("weather"):
            details = st.checkbox(
                "Show daily weather data and matching details", key="weather_details"
            )
            reader.validate(descriptor)
            weather_view(
                cached_weather(
                    cache_identity(descriptor, filters, "all", 1, 500),
                    descriptor,
                    filters,
                    details,
                    reader,
                ),
                minimum,
            )
        else:
            st.info("Weather data is not available in this dataset.")
    except Exception:
        st.error("Results are unavailable or the dataset has changed. Please reload the page.")
        st.stop()
    if task in (TASKS[0], TASKS[1]):
        with st.expander("Arrival delays: typical flights and the longer delays"):
            for col, title, key in zip(
                st.columns(3),
                ["Typical (median)", "Average", "90th percentile"],
                ["SIGNED_MEDIAN", "SIGNED_MEAN", "SIGNED_P90"],
                strict=True,
            ):
                col.metric(title, arrival_timing(summary[key]))
            st.write(
                "The median is the middle flight; the average is pulled up by long delays. "
                "About 90% of arrivals had a delay at or below the 90th percentile. "
                "Early arrivals count as negative minutes; cancellations and diversions "
                "are excluded. This is not a measure of passenger delay."
            )
    with st.expander("About the data and measures"):
        table(
            [
                {
                    "Measure": name,
                    "Eligible": summary[den],
                    "Excluded": summary["SCHEDULED_ROWS"] - summary[den],
                }
                for name, (_, den) in RATES.items()
            ]
        )
        table(
            [
                {
                    "Unknown arrival indicator": summary["UNKNOWN_ARRIVAL"],
                    "Unknown departure indicator": summary["UNKNOWN_DEPARTURE"],
                    "Unknown cancellation flag": summary["UNKNOWN_CANCELLED"],
                    "Unknown diversion flag": summary["UNKNOWN_DIVERTED"],
                    "Signed eligible": summary["SIGNED_ARRIVAL_COUNT"],
                }
            ]
        )
        st.write(
            "Source: US Department of Transportation airline reports. Each record is a "
            "reported scheduled flight, not a passenger journey. Percentages count matching "
            "flights directly, rather than averaging airline or monthly percentages. "
            "Airlines serve different routes and schedules, so these results do not prove "
            "that one airline or a weather condition caused a difference."
        )
        st.caption(
            f"Available dates: {options['start']}–{options['end']}. "
            "Flight counts and missing-data details are shown above."
        )


def main():
    st.set_page_config(page_title="Airline Delay Intelligence", layout="wide")
    try:
        path = os.environ.get("AIRLINE_DEVELOPMENT_CANDIDATE")
        with connect_as("reader") as connection:
            render(Reader(connection, Path(path) if path else None))
    except Exception:
        st.error("Cannot connect to the flight data. Please try again later.")
