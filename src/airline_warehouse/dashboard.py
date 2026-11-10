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
    airline_label,
    airport_label,
    arrival_timing,
    comparison_table,
    group_label,
    number,
    ordered_rows,
    percent,
    percent_value,
    prior_year,
    sort_comparisons,
    weather_coverage,
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


def plot(rows, label, value, *, order=None, horizontal=True, rate=False, tooltip_fields=()):
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
                *[alt.Tooltip(f"{field}:N") for field in tooltip_fields],
                alt.Tooltip(f"{value}:Q", format=".1%" if rate else ",.1f"),
            ],
        )
        .properties(height=max(180, len(rows) * 32) if horizontal else 270)
        .configure_axis(labelColor="#334155", titleColor="#16354A", labelFontSize=12)
        .configure_legend(labelColor="#334155", titleColor="#16354A")
    )
    st.altair_chart(chart, width="stretch")


def comparison(rows, group, summary, minimum, locations=None):
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
            st.caption(
                "Chosen from the 500 busiest groups. "
                "Use the route filters to focus on a specific journey."
            )
    if len(rows) != len(eligible):
        st.caption(
            f"{len(rows) - len(eligible)} groups have fewer than {minimum:,} flights "
            "with the data needed for this measure; their chart values are left blank."
        )
    group_title = {"carrier": "Airline", "route": "Route", "airport": "Airport"}.get(group, "Group")
    plot(
        [
            {
                group_title: group_label(r, group),
                **(
                    {"Location": group_label(r, group, locations)}
                    if group in ("route", "airport")
                    else {}
                ),
                metric: r[field] if r[denominator] >= minimum else None,
            }
            for r in selected
        ],
        group_title,
        metric,
        horizontal=not temporal,
        rate=True,
        tooltip_fields=("Location",) if group in ("route", "airport") else (),
    )
    compact = comparison_table(selected, group, locations)
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
    table([{group_title if k == "Group" else k: r[k] for k in primary} for r in compact])


def disruption(data, minimum):
    s = data["summary"]
    st.subheader("What types of delay were reported?")
    st.caption(
        f"Reported delay minutes across {number(s['CATEGORY_COMPLETE'])} arrivals "
        "at least 15 minutes late. A flight can have more than one reported reason."
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
    st.subheader("Cancellation reasons")
    st.caption("Share of cancelled flights by reported reason.")
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
        "Among flights departing at least 15 minutes late and reaching their planned destination. "
        "Making up time does not always mean arriving on time."
    )
    if 0 < s["CATEGORY_COMPLETE"] < minimum or 0 < s["RECOVERY_ELIGIBLE"] < minimum:
        st.warning("One of these comparisons is based on fewer flights than your selected minimum.")


def weather_view(data, minimum, selected_days=None, coverage=None):
    variable = st.selectbox(
        "Weather variable",
        ["temperature", "wind", "visibility"],
        format_func=lambda x: {
            "temperature": "Temperature (°C)",
            "wind": "Wind (m/s)",
            "visibility": "Visibility (m)",
        }[x],
        help="Each variable uses its own accepted observation at or before scheduled departure, "
        "no more than one hour old. Missing weather remains unmatched.",
    )
    st.subheader(f"Departure delays and cancellations by {variable}")
    st.caption("Each row groups selected flights by the weather near their scheduled departure.")
    rows = [r for r in data["comparisons"] if r["VARIABLE"] == variable]
    bands = WEATHER_BANDS[variable]
    rows.sort(key=lambda r: bands.index(r["BAND"]) if r["BAND"] in bands else len(bands))
    display = []
    for r in rows:
        dates, schedules, departures = weather_support(r, minimum)
        display.append(
            {
                "Band": r["BAND"],
                "Departure delayed": percent_value(r["DEPARTURE_DELAY_RATE"]),
                "Cancelled": percent_value(r["CANCELLATION_RATE"]),
                "Scheduled": r["SCHEDULED_ROWS"],
                "Dates": r["LOCAL_DATES"],
                "Support": "Limited" if not all((dates, schedules, departures)) else "Sufficient",
            }
        )
    table(display)
    if rows and selected_days is not None and selected_days < 5:
        st.warning(
            f"You selected only {selected_days} days. "
            "Use a longer period for a stronger comparison."
        )
    elif any(not all(weather_support(r, minimum)) for r in rows):
        st.warning("Some conditions have limited data; compare them with care.")
    st.caption("These comparisons show associations, not proof that weather caused a disruption.")
    coverage = [r for r in data["selected_coverage"] if r["VARIABLE"] == variable]
    total = sum(r["SCHEDULED_ROWS"] for r in coverage)
    matched = sum(r["MATCHED_ROWS"] for r in coverage)
    if total:
        st.caption(
            f"Weather matched for {matched / total:.1%} of selected flights "
            f"· {number(total - matched)} without a match."
        )


def render(reader):
    st.markdown(
        """<style>
    [data-testid="stMetricValue"] {font-size:1.8rem; white-space:normal; overflow:visible}
    [data-testid="stMetricLabel"] p {white-space:normal; overflow:visible}
    [data-testid="stCaptionContainer"] {opacity:1; color:#475569}
    [data-testid="stCaptionContainer"] p {color:#475569; font-size:0.9rem}
    .st-key-selection-summary {background:#F3F9FC; border-radius:16px}
    .st-key-selection-summary [data-testid="stCaptionContainer"] p
      {font-size:0.75rem; font-weight:600; letter-spacing:0.06em}
    .st-key-headline-metrics [data-testid="stMetric"]
      {background:#F8FCFE; border-top:3px solid #167D8D; border-radius:14px}
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
        "group": "route",
    }
    coverage = weather_coverage(descriptor.get("weather"))
    if coverage:
        start, end = max(coverage.start, options["start"]), min(coverage.end, options["end"])
        coverage = (
            replace(coverage, start=start, end=end)
            if start <= end and coverage.origin_id in dict(options["airports"])
            else None
        )

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

    def align_weather():
        if coverage is None:
            return
        st.session_state.dates = (coverage.start, coverage.end)
        st.session_state.origin = coverage.origin_id
        st.session_state.destination = None
        st.session_state.carriers = []
        st.session_state.period = "Custom"

    def custom_dates():
        st.session_state.period = "Custom"

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    carriers, airports = dict(options["carriers"]), dict(options["airports"])
    locations = {
        (airport_id, code): city for airport_id, code, city in options.get("airport_locations", [])
    }

    def label(v):
        return "All" if v is None else airport_label(v, airports[v], locations)

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
            format_func=lambda v: airline_label(v, carriers[v]),
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
        if task == TASKS[3] and coverage:
            st.button(f"Use DEN · {coverage.label}", on_click=align_weather)
        st.caption(
            "Filters update the results immediately. Choose a preset or enter your own dates."
        )
    if len(dates) != 2:
        st.info("Select both dates before querying.")
        st.stop()
    filters = Filters(dates[0], dates[1], tuple(chosen), origin, destination)
    st.header(task)
    with st.container(border=True, key="selection-summary"):
        for col, title, value in zip(
            st.columns([1, 1, 1.4]),
            ["TRAVEL DATES", "AIRLINES", "JOURNEY"],
            [
                f"{dates[0]:%d %b %Y} – {dates[1]:%d %b %Y}",
                ", ".join(airline_label(c, carriers[c]) for c in chosen) or "All airlines",
                "All routes"
                if origin is None and destination is None
                else f"{label(origin) if origin is not None else 'All origins'} → "
                f"{label(destination) if destination is not None else 'All destinations'}",
            ],
            strict=True,
        ):
            col.caption(title)
            col.write(value)
    if task == TASKS[3]:
        if coverage is None:
            st.warning("Weather data is unavailable: this release has no supported weather scope.")
            st.stop()
        st.info(
            f"Weather is available for Denver departures · {coverage.label}. "
            "You can narrow this to an airline, destination or dates within that period."
        )
        if not weather_scope(filters, descriptor.get("weather")):
            st.warning(
                "Your current filters are outside this weather study. "
                f"Select Denver within {coverage.label} to see matching flight and weather results."
            )
            st.button(
                f"Align filters to DEN · {coverage.label}", on_click=align_weather, type="primary"
            )
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
        if task == TASKS[0]:
            st.subheader("Selection overview")
            with st.container(key="headline-metrics"):
                headline_columns = st.columns(4)
            for col, (name, (field, denominator)) in zip(
                headline_columns, RATES.items(), strict=True
            ):
                col.metric(
                    {
                        "Arrival on-time": "On-time arrivals",
                        "Cancellation": "Cancelled",
                        "Diversion": "Diverted",
                        "Departure delay ≥15 min": "Late departures (15+ min)",
                    }[name],
                    percent(summary[field]),
                    help={
                        "ARRIVAL_RATE": "Arrived less than 15 minutes late. Excludes cancelled "
                        "and diverted flights and unknown arrival status.",
                        "CANCELLATION_RATE": "The percentage of scheduled flights "
                        "that were cancelled.",
                        "DIVERSION_RATE": "Diverted flights as a percentage "
                        "of all scheduled flights.",
                        "DEPARTURE_RATE": "Departed at least 15 minutes late. "
                        "Excludes cancellations and unknown departure status; "
                        "includes flights later diverted.",
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
            group = st.radio(
                "Explore by",
                ["route", "hour", "weekday", "month", "airport"],
                key="group",
                horizontal=True,
                format_func=lambda g: {
                    "month": "Month",
                    "weekday": "Day of week",
                    "hour": "Departure hour",
                    "route": "Routes",
                    "airport": "Departure airport",
                }[g],
            )
            if group == "route":
                st.caption(
                    "Compare routes here. Set Origin and Destination in the filters "
                    "to compare both directions of a specific route."
                )
            if not (group == "route" and origin is not None and destination is not None):
                comparison(metrics(group=group), group, summary, minimum, locations)
            if group == "hour":
                st.caption(
                    "Hours use scheduled local departure time. Source 2400 is kept "
                    "as a separate midnight bucket because its date is not inferred."
                )
            if group == "route" and origin is not None and destination is not None:
                st.subheader("Both route directions · same dates and airlines")
                reverse = metrics(replace(filters, origin=destination, destination=origin))[0]
                table(
                    comparison_table(
                        [
                            {
                                **summary,
                                "ORIGIN_ID": origin,
                                "DESTINATION_ID": destination,
                                "ORIGIN_LABEL": airports[origin],
                                "DESTINATION_LABEL": airports[destination],
                            },
                            {
                                **reverse,
                                "ORIGIN_ID": destination,
                                "DESTINATION_ID": origin,
                                "ORIGIN_LABEL": airports[destination],
                                "DESTINATION_LABEL": airports[origin],
                            },
                        ],
                        "route",
                        locations,
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
            reader.validate(descriptor)
            weather_view(
                cached_weather(
                    cache_identity(descriptor, filters, "all", 1, 500),
                    descriptor,
                    filters,
                    False,
                    reader,
                ),
                minimum,
                selected_days=(filters.end - filters.start).days + 1,
                coverage=coverage,
            )
        else:
            st.info("Weather data is not available in this dataset.")
    except Exception:
        st.error("Results are unavailable or the dataset has changed. Please reload the page.")
        st.stop()
    if task == TASKS[0] or (task == TASKS[1] and group != "route"):
        st.subheader("Arrival delays")
        for col, title, key in zip(
            st.columns(3),
            ["Typical (median)", "Average", "90th percentile"],
            ["SIGNED_MEDIAN", "SIGNED_MEAN", "SIGNED_P90"],
            strict=True,
        ):
            col.metric(
                title,
                arrival_timing(summary[key]),
                help=f"Based on {number(summary['SIGNED_ARRIVAL_COUNT'])} arrivals "
                "with known delay, excluding cancellations and diversions.",
            )
        st.caption(
            "Typical is the middle arrival; long delays pull up the average. "
            "About 90% of arrivals had a delay no greater than the 90th percentile."
        )


def main():
    st.set_page_config(page_title="Airline Delay Intelligence", layout="wide")
    try:
        path = os.environ.get("AIRLINE_DEVELOPMENT_CANDIDATE")
        with connect_as("reader") as connection:
            render(Reader(connection, Path(path) if path else None))
    except Exception:
        st.error("Cannot connect to the flight data. Please try again later.")
