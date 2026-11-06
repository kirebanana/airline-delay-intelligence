# Exploring the dashboard

The dashboard is a local Streamlit application backed by the existing published
Snowflake release. Use the protected reader configuration and launch instructions
in the [README](../README.md). Opening the dashboard does not ingest, refresh or
publish data. One release descriptor is reused throughout each render.

## Four investigations

- **Network & carriers:** begin with all 2023–2025 schedules. Compare on-time,
  cancellation, diversion, scheduled volume and signed p90 delay together. Change
  the comparison or trend metric; do not infer a universally best carrier from
  punctuality alone. Networks and schedules differ.
- **Time & routes:** choose month, weekday, scheduled hour, directional route or
  origin airport. Use the year/month preset and carrier/origin/destination filters.
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
  pilot. Explore temperature, wind or visibility separately. Inspect departure
  eligibility, cancellations, date support, largest-date concentration and missing
  matches. Full-pilot qualification stays in separate expandable detail. This is
  scheduled weather context, not national weather or a causal explanation.

## Controls and interpretation

Filters apply immediately; **Reset filters** restores baseline dates, all carriers,
all endpoints, the default support threshold and month grouping. Custom dates are
authoritative. The applied-scope line identifies the queried population. On narrow
screens, open or collapse Streamlit's sidebar to access filters or focus on results.

Chart comparisons use metric-specific minimum observations. Route/airport displays
show a bounded set selected by scheduled volume, with represented schedule share;
detail is capped at the largest 500 groups. This is not a global best/worst ranking.
Numeric comparison columns remain sortable; detailed support and signed-delay
summaries are expandable. Missing/zero-denominator metrics are unavailable, not zero.

Arrival on-time excludes cancelled/diverted and unknown ordinary-arrival indicators.
Cancellation/diversion rates use all schedules. Departure delay includes eligible
diversions. Signed delays retain early arrivals. Quantiles are computed on eligible
flight values, never averaged from subgroup quantiles. Source rows do not represent
passengers or distinct journeys.

Methodology, unknown observations, eligible counts and release provenance remain
available at the bottom of each investigation. Product acceptance does not waive
the separately documented infrastructure/security limitations.
