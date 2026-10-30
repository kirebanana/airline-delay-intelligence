# Complete baseline preparation and validation

**Ticket14 in progress.** The presenter still reads the validated January release;
the full 2023–2025 baseline is not yet declared accepted or published.

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

Full-source profile results, newly discovered critical allocation exceptions,
withheld-month addition, independent full-reader reconciliation and measured
full-scale costs remain completion gates—not conclusions of the small fixtures.

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
