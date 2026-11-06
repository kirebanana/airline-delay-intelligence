# Dashboard product improvements

**Status: scope and final focused corrections approved by owner, 2026-11-06;
implementation complete; final owner product acceptance pending.**
This bounded UI/analytics improvement batch supplements the
[project specification](airline-delay-intelligence.md). Final product acceptance is
separate from implementation and from infrastructure/security acceptance.

## Approved scope

Correct reset/widget synchronization, numeric hour ordering and metric-specific
weather support wording. Present carrier reliability trade-offs, bounded
volume-selected route/airport comparisons with population disclosures, chronological
time exploration, equivalent prior-year periods and route reversal. Shape category,
cancellation and signed-recovery evidence without changing population definitions.

Organize the existing Streamlit dashboard into Network & carriers, Time & routes,
Disruption & recovery, and DEN weather investigation. Query only the active task's
analytical sections. Retain one pinned release per render, validation before cached
results, restricted reader access and existing metric definitions.

No new framework, models, cloud resources, ingestion, refresh, data publication or
deployment is authorized by this batch. Existing unrelated working changes are not
part of it. No causal inference, composite carrier score or passenger-impact estimate.

## Acceptance

- Real browser reset clears visible carrier/route/dates and restores national counts;
  subsequent filtering cannot resurrect old selections.
- Rendered hours follow 0–23, with source 2400 explicit; weekdays ordered/named.
- Carrier punctuality, cancellation, diversion, volume and signed tail delay are
  readable together; metric eligibility remains accessible.
- Route/airport charts have a bounded plot count and disclose volume selection and
  represented schedules, never imply complete-network best/worst rankings.
- Prior-year comparison preserves carrier/route filters, uses aggregate counts,
  discloses leap-day handling and refuses incomplete reference coverage.
- Category minutes, affected-flight rates, cancelled-row reasons and signed recovery
  retain their distinct units/populations; missing observations remain visible.
- DEN coverage separates full pilot qualification from filtered context and uses
  scheduled versus departure-eligible support accurately.
- All four tasks work in a real browser. KPI values remain fully visible at 1440,
  900 and 600px. Automated regression tests supplement, not replace, visual evidence.
- Bounded released-data checks preserve established rates/quantiles. A fresh
  independent product review critiques the revised UI before owner acceptance.

## Design decisions / trade-offs

Preserve Streamlit and the query/publication architecture. Active-task lazy reads
reduce unrelated query fan-out; immutable-release options can cache for 15 minutes
while release-token validation still runs before result use. Immediate filters keep
visible controls aligned with results; no invisible draft/applied filter split.
Comparisons remain descriptive and unadjusted for traffic mix. A prior-year period
maps inclusive calendar dates, clamping February 29 to February 28 explicitly.

No owner acceptance is inferred from passing tests or an independent review.

## Validation outcome — 2026-11-06

Automated discovery: 142 tests, 111 passed and 31 opt-in live skips; lint/format
checks passed. Actual released-data browser validation exercised all four tasks,
combined filters, reset/subsequent edits, empty states, reverse routes and prior-year
comparisons at desktop, 900px and 600px. Twenty same-filter captured aggregate
results exactly matched the original dashboard; this is not a new raw-source audit.

A fresh independent browser-based product review rated the result 7.5/10 overall:
analytical quality 8, usability 7.5, presentation 7 and completeness 8.5. It confirmed
the reset/hour-order fixes, responsive KPIs and useful comparative capabilities,
but did **not** recommend unconditional acceptance. Outstanding findings:

- Formatted numeric strings in secondary tables sort lexicographically.
- Some horizontal charts suppress alternating group labels.
- Weather-task entry can foreground national flight KPIs above fixed-pilot results.
- Weather bands need physical order; airport primary detail should include its
  selected departure metric; weather/secondary caching can avoid threshold-driven
  refetches and eager collapsed diagnostics.

The owner subsequently authorized one focused correction pass, not another redesign.
Numeric cells now remain numeric and are formatted by column; categorical horizontal
axes explicitly retain all labels. Weather-task entry requires DEN-origin dates
contained in January 2025 before displaying any KPIs, with a prominent explicit
alignment action rather than silently changing the user's filters. Weather bands
follow physical order, with unmatched last. Airport primary detail includes the
selected metric and support. Threshold-independent secondary/weather cache keys
avoid refetching unchanged results; core weather reads omit full-pilot/daily
diagnostics until requested (six core versus twelve detailed aggregate queries).

Regression coverage includes numeric ordering, label-axis configuration, weather
scope boundaries, threshold cache reuse and diagnostic query counts. No metric
definitions, dbt models or publication/infrastructure boundaries changed.
Final refinement validation: 146 automated tests (115 passed, 31 opt-in live skips),
lint/format passed. Actual browser interaction confirmed ascending numeric category
sorting, complete carrier labels at 1440/900/600px, bounded route/airport detail,
weather entry/alignment, physical band order and threshold support. Sixteen matching
captured aggregate results remained unchanged. Changing the weather threshold
reused the cached weather result; requesting diagnostics performed the additional
read explicitly. No further independent-review cycle was run.
Screenshots/internal review evidence stay in
ignored workspace scratch storage. No application deployment or data processing
was performed by this local implementation/validation cycle.
