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
    comparison_table,
    group_label,
    number,
    ordered_rows,
    percent,
    prior_year,
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
            self.connection, descriptor, filters, development=descriptor.get("development", False)
        )

    def weather(self, descriptor, filters):
        return query_weather(
            self.connection, descriptor, filters, development=descriptor.get("development", False)
        )


def table(rows):
    if rows:
        configs = {}
        for key in rows[0]:
            if any(isinstance(r.get(key), str) for r in rows):
                continue
            if key in ("On-time", "Cancelled", "Diverted", "Departure delayed"):
                configs[key] = st.column_config.NumberColumn(format="%.1f%%")
            elif key in ("Scheduled", "Arrival eligible", "Departure eligible", "Signed eligible"):
                configs[key] = st.column_config.NumberColumn(format="%,d")
            elif key in ("Median min", "p90 min"):
                configs[key] = st.column_config.NumberColumn(format="%.1f")
        st.dataframe(rows, hide_index=True, width="stretch", column_config=configs)
    else:
        st.info("No observations for this selection. N/A is not zero performance.")


def plot(rows, label, value, *, order=None, horizontal=True, rate=False):
    if not rows or not any(r.get(value) is not None for r in rows):
        st.info("No eligible observations to chart.")
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
                    f"{label}:N", sort=order or list(frame[label]), title=None
                ),
                "x" if horizontal else "y": measure(
                    f"{value}:Q", title=value, axis=alt.Axis(format=".0%" if rate else "~s")
                ),
            },
            tooltip=[
                alt.Tooltip(f"{label}:N"),
                alt.Tooltip(f"{value}:Q", format=".1%" if rate else ",.1f"),
            ],
        )
        .properties(height=max(180, len(rows) * 27) if horizontal else 270)
    )
    st.altair_chart(chart, width="stretch")


def comparison(rows, group, summary, minimum):
    st.subheader(
        "Compare "
        + {"carrier": "carriers", "airport": "origin airports", "route": "directional routes"}.get(
            group, group
        )
    )
    metric = st.selectbox(
        "Comparison metric",
        list(RATES),
        key=f"metric_{group}",
        index=3 if group == "airport" else 0,
    )
    field, denominator = RATES[metric]
    temporal = group in ("month", "weekday", "hour")
    count = 36 if temporal else st.slider("Groups to plot", 5, 30, 10, key=f"top_{group}")
    ordered = ordered_rows(rows, group)
    eligible = [r for r in ordered if r[denominator] >= minimum]
    selected = ordered if temporal else eligible[:count]
    if not temporal:
        shown = sum(int(r["SCHEDULED_ROWS"]) for r in selected)
        total = int(summary["SCHEDULED_ROWS"])
        st.caption(
            f"Largest {len(selected)} qualifying groups by scheduled volume, not best/worst. "
            f"Plotted schedules: {shown:,} / {total:,} ({shown / total:.1%})."
            if total
            else "No schedules."
        )
        if group in ("route", "airport"):
            st.caption(
                "Detail is capped at the 500 largest groups by volume; "
                "this is not a whole-network performance ranking."
            )
    st.caption(
        f"Chart requires ≥{minimum:,} observations in the selected metric's denominator. "
        f"{len(rows) - len(eligible)} returned groups below support remain in detail."
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
    table([{k: r[k] for k in primary} for r in compact])
    with st.expander("All returned groups · eligibility and signed-delay summaries"):
        table(comparison_table(rows, group))
        st.caption(
            "Arrival rate excludes cancelled/diverted and unknown indicators. "
            "Signed median/p90 use eligible signed delays, not subgroup quantile averages. "
            "Unadjusted network/schedule mix differs."
        )


def disruption(data, minimum):
    s = data["summary"]
    st.subheader("Reported delay categories")
    st.write(
        f"Late ordinary arrivals: {number(s['CATEGORY_ELIGIBLE'])}; complete allocations: "
        f"{number(s['CATEGORY_COMPLETE'])}; missing: {number(s['MISSING_CATEGORY_ROWS'])}."
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
                "Reported minutes": number(r["Minutes"]),
                "Minute share": percent(r["Minute share"]),
                "Affected flights": percent(r["Affected"]),
            }
            for r in categories
        ]
    )
    st.caption(
        "Minute share divides by all reported category minutes on complete late-arrival "
        "allocations. Affected % divides by complete late arrivals; categories overlap "
        "and need not sum to 100%. Reported attributions are not proven causes. "
        "Weather is not all weather-associated disruption."
    )
    with st.expander("Allocation quality and exclusions"):
        st.write(
            "Excluded arrival-delay minutes on incomplete rows: "
            f"{number(s['EXCLUDED_ARRIVAL_MINUTES'])}; "
            f"allocation mismatches: {number(s['ALLOCATION_MISMATCH_ROWS'])}."
        )
        st.write("Cancelled/diverted and unknown arrival indicators are excluded.")
    if s["UNALLOCATED_MINUTES"]:
        st.warning(
            f"Unallocated arrival-delay minutes: {number(s['UNALLOCATED_MINUTES'])}; "
            "preserved, not repaired."
        )
    st.subheader("Cancellation reasons")
    st.caption(
        "Separate population: cancelled rows only, not late-arrival minutes. "
        "Unknown reasons retained."
    )
    reasons = [
        {
            "Reason": r["CANCELLATION_REASON"].replace("NAS", "National Airspace System (NAS)"),
            "Cancelled rows": number(r["CANCELLED_ROWS"]),
            "Share": percent(r["CANCELLED_SHARE"]),
        }
        for r in data["cancellations"]
    ]
    table(reasons)
    st.subheader("Schedule-relative recovery")
    st.metric("Late departures arriving below 15 minutes late", percent(s["RECOVERY_SHARE"]))
    st.write(
        f"Eligible late departures: {number(s['RECOVERY_ELIGIBLE'])}; "
        f"recovered: {number(s['RECOVERED'])}."
    )
    st.write(
        "Signed improvement (departure delay − arrival delay): "
        f"mean {number(s['IMPROVEMENT_MEAN'], ' min', 1)}, "
        f"median {number(s['IMPROVEMENT_MEDIAN'], ' min', 1)}, "
        f"p90 {number(s['IMPROVEMENT_P90'], ' min', 1)}."
    )
    bands = sorted(data["distribution"], key=lambda r: RECOVERY_ORDER.index(r["RECOVERY_BAND"]))
    distribution = [
        {
            "Improvement band": r["RECOVERY_BAND"],
            "Share": float(r["ELIGIBLE_ROWS"]) / s["RECOVERY_ELIGIBLE"]
            if s["RECOVERY_ELIGIBLE"]
            else None,
            "Flights": number(r["ELIGIBLE_ROWS"]),
        }
        for r in bands
    ]
    plot(distribution, "Improvement band", "Share", rate=True)
    table([{**r, "Share": percent(r["Share"])} for r in distribution])
    st.caption(
        "Ordinary noncancelled/nondiverted completions departing ≥15 min late with both "
        "signed delays known. Negative/zero improvement retained. Positive improvement "
        "is not proof of faster flying or a causal intervention."
    )
    st.write(
        "Missing arrival delay among ordinary late departures: "
        f"{number(s.get('RECOVERY_MISSING_ARRIVAL'))}. "
        "Missing departure delay among ordinary completions: "
        f"{number(s.get('RECOVERY_MISSING_DEPARTURE'))}. "
        "These diagnostics are distinct from scheduled rows that simply did not depart late."
    )
    if 0 < s["CATEGORY_COMPLETE"] < minimum or 0 < s["RECOVERY_ELIGIBLE"] < minimum:
        st.warning("A secondary subset is below the sample-size threshold; inspect support.")


def weather_view(data, minimum):
    st.caption(
        "Fixed DEN-origin, Denver-local January 2025 pilot, including cancellations/diversions. "
        "Latest accepted observation at/before scheduled departure, age ≤60 min. "
        "Variables may match different times."
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
    if not rows:
        st.info("No DEN pilot rows match these filters; national weather is not available.")
    display = []
    for r in rows:
        dates, schedules, departures = weather_support(r, minimum)
        display.append(
            {
                "Band": r["BAND"],
                "Departure delayed": percent(r["DEPARTURE_DELAY_RATE"]),
                "Cancelled": percent(r["CANCELLATION_RATE"]),
                "Scheduled": number(r["SCHEDULED_ROWS"]),
                "Departure eligible": number(r["DEPARTURE_DENOMINATOR"]),
                "Dates": r["LOCAL_DATES"],
                "Largest date": percent(r["LARGEST_DATE_SHARE"]),
                "Support": "Limited"
                if not all((dates, schedules, departures))
                else "Thresholds met",
            }
        )
    table(display)
    if any(not all(weather_support(r, minimum)) for r in rows):
        st.warning(
            f"Some bands have fewer than five local dates or fewer than {minimum:,} "
            "scheduled / departure-eligible observations. Support is metric-specific, "
            "not a performance ranking."
        )
    st.caption(
        "Inspect dates and largest-date share: flights sharing a date/episode are not "
        "independent weather events. Thresholds do not establish statistical independence "
        "or control traffic mix. Unmatched conditions are not benign. Cancellation selection "
        "and carrier/route/hour mix confound comparisons. Scheduled weather does not establish "
        "cancellation-decision conditions or causality. No compound conditions."
    )
    st.subheader("Filtered coverage · matched and missing observations")
    coverage = [r for r in data["selected_coverage"] if r["VARIABLE"] == variable]
    table(
        [
            {
                "Flight status": "Cancelled" if r["CANCELLED"] else "Not cancelled",
                "Scheduled": number(r["SCHEDULED_ROWS"]),
                "Matched": number(r["MATCHED_ROWS"]),
                "Coverage": percent(r["COVERAGE"]),
                "Unmatched": number(r["SCHEDULED_ROWS"] - r["MATCHED_ROWS"]),
            }
            for r in coverage
        ]
    )
    with st.expander("Full pilot qualification · unaffected by flight filters"):
        table(data["pilot_coverage"])
    with st.expander("Daily coverage and match-quality diagnostics"):
        table([r for r in data["daily"] if r["VARIABLE"] == variable])
        table(coverage)


def render(reader):
    st.markdown(
        """<style>
    [data-testid="stMetricValue"] {font-size:1.8rem; white-space:normal; overflow:visible}
    [data-testid="stMetricLabel"] p {white-space:normal; overflow:visible}
    @media (max-width:1100px) { [data-testid="stHorizontalBlock"] {flex-wrap:wrap}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]
      {min-width:210px; flex:1 1 210px} }
    </style>""",
        unsafe_allow_html=True,
    )
    st.title("Airline Delay Intelligence")
    st.caption(
        "Historical airline & network reliability · descriptive, not causal · "
        "source rows, not passengers"
    )
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
        st.error("Unavailable: no readable validated release. No privileged fallback.")
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
            "Period preset",
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
            "Marketing carrier", list(carriers), key="carriers", format_func=lambda v: carriers[v]
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
            "Chart minimum observations", min_value=1, max_value=1_000_000, step=1, key="minimum"
        )
        if task == TASKS[3]:
            st.button("Use DEN · January 2025", on_click=pilot)
        st.caption(
            "Changes apply immediately. Presets set dates; custom dates are authoritative. "
            "Comparisons are unadjusted for network and schedule mix."
        )
    if len(dates) != 2:
        st.info("Select both dates before querying.")
        st.stop()
    filters = Filters(dates[0], dates[1], tuple(chosen), origin, destination)
    st.header(task)
    st.caption(
        f"Applied: {dates[0]}–{dates[1]} · "
        f"{', '.join(carriers[c] for c in chosen) or 'All carriers'} · "
        f"{label(origin)} → {label(destination)}"
    )

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
                help=f"Eligible observations: {number(summary[denominator])}",
                border=True,
            )
        st.write(
            f"Scheduled source rows: **{number(summary['SCHEDULED_ROWS'])}** · "
            f"Arrival eligible: {number(summary['ARRIVAL_DENOMINATOR'])} · "
            f"Departure eligible: {number(summary['DEPARTURE_DENOMINATOR'])}"
        )
        st.caption(
            "On-time: <15 min among eligible ordinary arrivals; cancellations/diversions "
            "excluded. Cancellation/diversion rates use all schedules; "
            "departure delay includes eligible diversions."
        )
        if not summary["SCHEDULED_ROWS"]:
            st.info(
                "No observations match these filters. "
                "Zero denominators are N/A, not zero performance."
            )
        st.caption(
            f"Signed arrival delay · median {number(summary['SIGNED_MEDIAN'], ' min', 1)} · "
            f"mean {number(summary['SIGNED_MEAN'], ' min', 1)} · "
            f"exact p90 {number(summary['SIGNED_P90'], ' min', 1)}. Early arrivals stay negative."
        )
        if task == TASKS[0]:
            comparison(metrics(group="carrier"), "carrier", summary, minimum)
            st.subheader("Monthly reliability context")
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
                "Monthly rates use their own eligible counts. "
                "Missing/unsupported periods are not zero. "
                "Use Time & routes for equivalent-period comparisons."
            )
        elif task == TASKS[1]:
            group = st.selectbox(
                "Explore by", ["month", "weekday", "hour", "route", "airport"], key="group"
            )
            comparison(metrics(group=group), group, summary, minimum)
            st.caption(
                "Local scheduled hours, not actual/UTC departures. Source 2400 remains "
                "a separate bucket, not a next-day conversion. A→B differs from B→A."
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
                st.subheader("Equivalent-period comparison")
                st.caption(
                    f"Current {filters.start}–{filters.end}; "
                    f"reference {previous.start}–{previous.end}. Same carrier/route filters. "
                    "Leap day clamps to February 28; period lengths may differ. "
                    "Traffic mix is not adjusted."
                )
                table(
                    [
                        {
                            "Measure": name,
                            "Current": percent(summary[field]),
                            "Prior year": percent(reference[field]),
                            "Change (pp)": number(
                                (float(summary[field]) - float(reference[field])) * 100, decimals=2
                            )
                            if summary[field] is not None and reference[field] is not None
                            else "N/A",
                            "Current eligible": number(summary[den]),
                            "Prior eligible": number(reference[den]),
                        }
                        for name, (field, den) in RATES.items()
                    ]
                )
            if previous is None:
                st.caption(
                    "Choose a period whose full prior-year dates are within released coverage "
                    "to enable the comparator."
                )
        elif task == TASKS[2]:
            if descriptor.get("analytical_contract") == "secondary-v1" or descriptor.get(
                "development"
            ):
                reader.validate(descriptor)
                disruption(
                    cached_secondary(
                        cache_identity(descriptor, filters, "all", minimum, 500),
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
                    cache_identity(descriptor, filters, "all", minimum, 500),
                    descriptor,
                    filters,
                    reader,
                ),
                minimum,
            )
        else:
            st.info("This release does not contain the qualified DEN weather pilot.")
    except Exception:
        st.error(
            "Results unavailable or release token expired. "
            "Reload; no partial/new-release fallback was used."
        )
        st.stop()
    with st.expander("Methodology, eligibility & technical provenance"):
        table(
            [
                {
                    "Measure": name,
                    "Eligible": number(summary[den]),
                    "Excluded": number(summary["SCHEDULED_ROWS"] - summary[den]),
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
            "Rates use aggregate numerators/denominators, never averages of subgroup rates. "
            "Exact signed quantiles use eligible flight values. Marketing-table source rows "
            "are not passengers or distinct journeys. Stable IDs and original source labels "
            "remain on facts. Descriptive differences do not establish causation "
            "or fairness-adjusted rankings."
        )
        st.json(
            {
                k: str(descriptor.get(k))
                for k in ("release_id", "built_at", "published_at", "processing_contract")
            }
        )
        st.caption(
            f"Released coverage: {options['start']}–{options['end']}. "
            "One immutable descriptor per render; no unpublished fallback."
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
