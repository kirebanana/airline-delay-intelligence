# Exploring the dashboard

The dashboard is a local Streamlit application backed by the existing published
Snowflake release. Use the protected reader configuration and launch instructions
in the [README](../README.md). Opening the dashboard does not ingest, refresh or
publish data. One release descriptor is reused throughout each render.

## Four investigations

- **Network & carriers:** begin with all 2023–2025 schedules. Compare on-time,
  cancellation, diversion, scheduled volume and signed p90 delay together. Change
  the comparison or trend metric. All airlines in the selection are shown; use
  **Order by** to choose highest/lowest rate, most flights or alphabetical order.
  Names appear alongside codes in the chart, hover text, filter and main table.
  Display names use a checked BTS lookup snapshot matched on both DOT airline ID
  and code; unknown combinations retain their source code. The lookup provenance
  is packaged in `airline_names.json`; it is not a current airline registry.
  Do not infer a universally best carrier from
  punctuality alone. Networks and schedules differ.
- **Time & routes:** opens directly on routes. Visible choices switch to departure
  hour, day of week, month or departure airport. Use year/month and airline/airport filters.
  Route tables and chart hover text show cities with airport codes from the pinned
  release's airport dimension; compact chart axes retain codes. Unmatched identities
  keep their code rather than guess a location.
  With both endpoints selected, inspect both directions together or use **Reverse
  route**. A prior-year comparator is available only when the entire reference
  period is within released coverage. Changes are percentage points, not percent
  changes; leap-day clamping is disclosed beside the comparison.
- **Disruption & recovery:** category-minute shares and affected-flight rates have
  different units. Cancellation reasons use cancelled rows only. Recovery covers
  ordinary late departures with both signed delays known; negative improvement
  means the flight worsened. Arriving below 15 minutes late is distinct from any
  positive improvement.
- **DEN weather investigation:** **Use DEN · January 2025** selects the qualified
  pilot. When filters are outside that pilot, no KPIs/results appear; the main
  **Align filters to DEN · January 2025** action explicitly selects the pilot.
  Explore temperature, wind or visibility separately. Inspect departure
  eligibility, cancellations, date support, largest-date concentration and missing
  matches. The flight count covers all selected flights; the weather table splits them
  into condition groups. Selecting a different weather variable does not change
  the selected population. A two-day selection is explicitly flagged because many
  flights can share only one or two weather events. Changing support thresholds
  reuses the same analytical aggregates. Raw full-pilot/daily diagnostics are not
  shown. This is scheduled weather context, not national weather or a causal explanation.

## Controls and interpretation

Filters apply immediately; **Reset filters** restores baseline dates, all carriers,
all endpoints, the default support threshold and route grouping. Custom dates are
authoritative. Travel-date, airline and journey cards identify the queried population.
The **Selection overview** cards appear only on Network & carriers. The other
investigations retain the selection summary and scheduled-flight count, then lead
with their own comparisons or findings instead of repeating those four rates. On narrow
screens, open or collapse Streamlit's sidebar to access filters or focus on results.

Chart comparisons use the flights with the information needed for each measure.
The minimum-flights control can hide small-sample chart values without removing
their table rows. Route/airport displays
show a bounded set selected by scheduled volume, with represented schedule share;
detail is capped at the largest 500 groups. This is not a global best/worst ranking.
The chart and one main comparison table show the selected groups; there is no
duplicate expanded comparison table. Numeric columns remain sortable.
Missing/zero-denominator metrics are unavailable, not zero.

Arrival on-time excludes cancelled/diverted and unknown ordinary-arrival indicators.
Cancellation/diversion rates use all schedules. Departure delay includes eligible
diversions. Signed delays retain early arrivals. Quantiles are computed on eligible
flight values, never averaged from subgroup quantiles. Source rows do not represent
passengers or distinct journeys.

Short definitions are available beside headline measures. Arrival-delay summaries,
weather matching counts and low-support warnings are shown where they help
interpret the analysis. Operational reconciliation counts, repeated explanatory
footers, technical-detail expanders and raw diagnostics are
removed; internal release identifiers are not part of the dashboard. Product
acceptance does not waive the separately documented infrastructure/security limitations.
