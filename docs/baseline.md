# Complete baseline preparation and validation

**2026-11-01: ticket14 implementation qualified.** The
presenter now selects all36months of2023–2025 together with the fixed weather
pilot. Both the deliberately incomplete35-month release and ordinary36-month
addition pass independent original-archive versus restricted-reader checks.
Full-scale frozen-failure preservation, safe same-input replay and the real
dashboard also pass. This is not final cloud/platform acceptance.

## Explicit official acquisition

```bash
airline acquire --month 2024-05 --output /private/new-download --ranged
airline prepare --archive /private/new-download/source.zip --month 2024-05 \
  --expected-sha256 <selected-source-hash> --output /private/new-artifact
```

Acquisition requests one named BTS marketing archive, never an annual file or
automatic future-period discovery. It preserves the exact ZIP and retrieval URL,
time, checksum and validators. Original ZIP/schema/CRC and strict preparation
checks precede acceptance. Outputs are create-only; partial failures remain
diagnostic inputs, not accepted files. One canonical filename is selected per
month; the December2023 directory alias is not a second partition or a claim of
byte equivalence between unselected URLs.

Most initial archives succeeded with a single response. May2024 stalled after
23,789,568 retained bytes and exceeded its cooperative five-minute allowance;
that partial response was preserved, not appended to or accepted. A separately
deliberate, same-month ranged attempt completed in30.86seconds:35,024,172bytes,
full ZIP CRC/hash checks, matching old prefix and one strong ETag. The ranged
adapter uses a one-byte size/validator probe and at most three concurrent4MiB
requests, all pinned with If-Match and exact Content-Range checks. Changed or
unsupported validators fail closed. Remaining explicit baseline imports use this
qualified transport; there is no endless retry or alternate-source substitution.
HTTP checks are cooperative with a bounded socket tail; a complete artifact is
never accepted after the configured partition deadline.

## Partition and publication integrity

The candidate binds an exact artifact ID, original source hash, row count and
source kind for each selected month. Frozen validation reconciles each month's
source/artifact group, row count and complete ordinal range, not just the global
total or set of artifact IDs. A real two-month fixture proves that changing one
row's artifact assignment is rejected even though global counts, technical keys,
native source fingerprints and the set of artifact IDs remain correct.

Synthetic imports cannot replace the presenter target: both refresh preflight
and the publisher reject them before warehouse work. A complete36-month result
also requires its compatible fixed weather dependency. Test targets remain
isolated, and any required-stage failure retains the previous complete release.

## Scheduled source midnight

The broader census found BTS scheduled `2400` outside the fixed weather pilot.
It is retained as a separately labelled **source-midnight clock bucket**, not a
24th ordinary hour and not an inferred next-day timestamp. Native FlightDate and
all source values remain unchanged; rates and scheduled-row counts do not lose
those observations. A real failing/passing dbt fixture and query check establish
that the original date and clock survive. Other malformed clocks still fail.

This does not relax DEN/local-January anchor rules: a newly ambiguous pilot clock
still blocks weather acceptance until resolved, and no national UTC/DST or actual
event reconstruction is claimed.

The completed36-month census contains22,562,477rows, no candidate-key collisions,
no non-N duplicate indicators, no Flights values other than1.00 and no unknown
cancellation/diversion flags. The two scheduled2400rows are outside DEN/January.
There are4,680,953category-eligible rows:4,680,950with complete allocations and
three missing allocations (disclosed exclusions, never zero-filled).
Withheld-month addition, independent full-reader reconciliation and measured
full-scale execution are evidenced below, separately from the small fixtures.
Full-scale failure, replay and dashboard qualification are recorded below.

## Reviewed source allocation exception

The independent original-archive census identified UA2334, ORD→DCA,
2023-10-04: arrival delay231minutes with all five reported allocations zero.
Archive SHA256`68c5a96d28c6193a85e7257ba131faf0112b810c54e3a9fc38ff61cb66b5bfa0`,
source row416811, native row fingerprint
`276f51920a74634e164decea6802afb1176382e87e28c3d5429ef66daa98b849`.
The archive checksum and original row were independently re-read. Cancelled=0,
Diverted=0, ArrDel15=1, DepDelay=−5 and DivAirportLandings=9 remain exactly as
reported. The sentinel is not interpreted as a cancellation or a replacement
diversion flag; no cause is invented for the231minutes.

Independent specification review on2026-10-30 confirmed that this exact-evidence
exception is within the existing PRD§8.1/D06 technical review policy, not a new
population or metric rule. The integrity gate now recognizes this exact source
triple alongside the already reviewed January2024 row. All other field checks
still apply. A real Snowflake predicate test accepts the exact triple and rejects
each changed archive hash, row ordinal or row fingerprint. Unallocated minutes
remain visible in the existing category reconciliation summary; reported-minute
shares use only the actual allocations. New mismatches still block publication.

The completed census found fourteen further rows of this same source anomaly
class. A separate native-archive re-read verified all sixteen identities, flags,
signed delays and all-five-zero allocations. All have DivAirportLandings=9 but
Cancelled=0/Diverted=0; the native flags remain authoritative. The exact triples
are maintained only in [the shared integrity gate](../dbt/tests/secondary_integrity.sql).
The complete scoped exception inventory is:

| Source month | Row | Flight date | Flight | Route | Unallocated minutes |
| --- | ---: | --- | --- | --- | ---: |
| 2023-10 | 416811 | 2023-10-04 | UA2334 | ORD→DCA | 231 |
| 2024-01 | 432835 | 2024-01-21 | UA4813 | IAH→BRO | 1345 |
| 2025-09 | 370558 | 2025-09-08 | WN1671 | FLL→BWI | 75 |
| 2025-10 | 382201 | 2025-10-30 | WN3884 | LAS→SAN | 198 |
| 2025-10 | 441145 | 2025-10-28 | WN159 | ABQ→DEN | 99 |
| 2025-11 | 521583 | 2025-11-26 | WN2143 | BNA→PNS | 137 |
| 2025-11 | 529535 | 2025-11-30 | WN2466 | DEN→HDN | 334 |
| 2025-11 | 551098 | 2025-11-20 | WN1866 | DEN→AUS | 93 |
| 2025-11 | 551665 | 2025-11-20 | WN2921 | LAS→BOI | 813 |
| 2025-11 | 553361 | 2025-11-20 | WN4353 | SMF→BOI | 820 |
| 2025-11 | 554832 | 2025-11-21 | WN3051 | DEN→BZN | 277 |
| 2025-11 | 559464 | 2025-11-24 | WN981 | DEN→BZN | 118 |
| 2025-11 | 563067 | 2025-11-26 | WN4657 | STL→CMH | 188 |
| 2025-11 | 594240 | 2025-11-17 | WN2537 | LAS→BUR | 189 |
| 2025-11 | 597291 | 2025-11-18 | WN2827 | DEN→HOU | 98 |
| 2025-11 | 599553 | 2025-11-18 | WN3994 | SMF→ONT | 130 |

Total unallocated minutes:5,145. This is not added to any reported category.
The isolated live predicate qualification covers each exact triple and separately
changes each of its three identifiers; full native-field/fingerprint checks remain
additional required build/publication gates.

## Published baseline and independent reconciliation

| Ordinary refresh | Selected rows | Release | Intent→result |
| --- | ---: | --- | ---: |
| 35months, withholding2025-12 | 21,917,490 | `3552cea5c97c4b558b013e5ff70c1ad4` | 998.77s |
| 36months, adding2025-12 | 22,562,477 | `02d263d7f7174890b6da97c15a81d098` | 519.08s |

The added month contributes644,987rows. The other35selected artifact/source
identities, processing contract and fixed weather artifact remain unchanged.
Original ZIPs, prepared payloads, manifests, retrieval evidence and weather
references are retained in private Ohio S3:149objects/3,394,721,176bytes. Independent
HEAD checks verified every full-object SHA256, length and AES256 setting; retries
were conditional, not overwrites. No IAM, bucket-policy, warehouse or monitor
changes were made.

An independent original-archive oracle matches each released result, including
all four populations, unknown exclusions, exact signed/recovery quantiles, all
category minutes/counts, cancellation reasons, recovery bands and carrier/month/
weekday/hour/origin/DEN-directional-route populations. The complete result has
22,189,768ordinary-arrival indicator/signed-delay observations,17,508,815on-time
arrivals,314,973cancellations and57,734diversions. There are two unknown arrival
indicators, not inferred on-time flights. Signed arrival mean/median/p90 are
7.4045414535/−6/44minutes. Recovery eligibility is4,587,535with878,883recovered;
signed improvement mean/median/p90 are4.2281865969/7/21minutes.

All24,732DEN-pilot rows remain together, including313cancellations and69diversions.
Matched temperature/wind/visibility counts remain24,585/24,683/24,380. National
coverage does not expand or relax the fixed pilot's station, time, quality or
age rules. Methodology remains in [analytics](analytics.md),
[categories/recovery](secondary-analytics.md), [weather](weather.md) and
[attended recovery](local-recovery.md); the [README diagram](../README.md#architecture)
describes the implemented local/S3/Snowflake path.

## Measured finite execution and costs

Both full builds used the unchanged X-Small warehouse, two dbt threads and the
existing45-minute run/five-minute publication/600-second SQL bounds. dbt build
time was236.12s/239.86s; the longest36-month dbt node was90.90s. No resizing or
automatic limit increases were needed. The36-month driver took574.67s including
local artifact verification and before/after metadata reads; intent→result above
is a narrower interval, not billed warehouse uptime.

After the35-month refresh, selected RAW tables reported1,977,866,240compressed
logical bytes and candidate tables5,783,546,880bytes. These are not unique physical
storage or total retained-clone/time-travel billing. The36-month account-monitor
observation increased3.89→4.11credits, leaving0.89of5. This rounded/lagged shared
account delta is not exact per-job billing and excludes retained-storage charges.
The0.5-credit recovery reserve remains; no monitor reset/increase is authorized.
After final qualification the monitor reported4.46used/0.54remaining. This is
close to the unchanged0.5-credit recovery reserve: do not start further warehouse
data work without checking the remaining allowance and obtaining an exact owner
adjustment if needed. The selected target has no owner/request or unresolved
recovery flag; final metadata showed no running/queued warehouse statements.

## Final failure, replay and dashboard qualification

The full-scale negative test passed in95.79s. One derived recovery value was
changed only in a new clone. Ordinary refresh with unchanged declared dependencies
correctly reused the good complete release; direct frozen publication rejected
the clone, retired that exact failed authority, and retained the entire active
descriptor, weather dependency and22,562,477-row restricted-reader result. No
accepted source/current-work/released row was changed. The first test attempt
incorrectly expected the safe reuse path to raise; the test was corrected to
exercise both boundaries. This is not a full-scale changed-input rebuild failure
claim. The representative changed-input rejection/correction/clean rebuild and
repacked-input suite separately passed535.70s with the current processing contract.

A subsequent ordinary full-baseline same-input refresh reused
`02d263d7f7174890b6da97c15a81d098` without creating another candidate. The before/
after withheld-month comparison confirms644,987added rows and unchanged other
input bindings, processing contract and fixed weather artifact; both releases
have independent reader reconciliations.

The real restricted-reader Streamlit AppTest passed all six views, DEN filtering,
reset, full released labeling, and error checks. Initial application-cache-cold/
warm renders took23.69s/5.17s; individual grouped views3.34–7.68s and DEN filtering
16.78s. Application caches were cleared and Snowflake query-result reuse disabled;
initial warehouse state was recorded, not forcibly suspended. These are not a
warehouse-cold benchmark or a production SLA. Local-only presentation remains;
no inbound endpoint or hosted dashboard was introduced.

Final offline discovery:78tests,47executed and31explicit live skips. Ruff checks/
formatting and dbt parse pass. Independent Standards and Spec reviews found no
blocking defects; scoped source exceptions were separately reviewed. Original
analytical contracts and the [architecture diagram](../README.md#architecture)
remain authoritative. AWS container/orchestration/deployment and final project
acceptance remain later tickets, not conclusions of this data milestone.
