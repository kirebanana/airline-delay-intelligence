# Reported categories and signed recovery

Implemented 2026-10-30 against the existing January-only milestone. This is not
36-month acceptance. Eligibility, category values, cancellation labels, signed
improvement and distribution bands live in dbt's flight-grain fact. The exposed
dashboard consumer filters released fields before Snowflake counts/exact quantiles.
No chart-grain models or new service were added.

Category eligibility is ordinary noncancelled/nondiverted known late arrivals.
Minute shares and positive-allocation rates both use the complete five-category
subset; missing rows and their known arrival minutes are separately reported.
Unknown/negative/malformed allocations and new complete reconciliation failures
block acceptance. Exactly one reviewed 1,345-minute unallocated row is allowlisted
by archive hash, ordinal **and full source-row fingerprint**, not a broad zero rule.
Cancellation reasons use cancelled rows only, retaining unknown codes. Diversion
sentinels never replace the source cancellation flag.

Recovery eligibility is ordinary completions departing ≥15 minutes late with both
signed delays known. Improvement is departure minus arrival delay; zero/negative
values remain. Recovered means arrival delay <15. Rates use eligible counts and
continuous median/p90 use filtered eligible values. No causal/faster-flight claim.

Independent January archive reconciliation: 109,605 eligible/complete category
rows; reported minutes 7,872,217; recovery 105,107 eligible, 22,893 recovered,
mean improvement 4.6314422446, median 8, p90 23 minutes. Real hand-authored SQL
fixtures cover overlapping categories, incomplete allocations, empty scopes,
cancellation unknowns and signed improvement 6/15/0/−5. A real isolated frozen
corruption test preserves the previous release and reads the good result using
the restricted reader. Full pilot/publication status is recorded in the weather
runbook once qualified; old releases do not claim newly added analytical fields.

Default offline discovery skips live tests. Explicit qualification uses
`AIRLINE_SECONDARY_LIVE=funded-11`, a reviewed `AIRLINE_TEST_CANDIDATE` and
`AIRLINE_BATCH_STATE` with `tests/test_live_secondary.py`. Never opt in without
funding and isolated fixture approval. The dashboard remains loopback-only.
