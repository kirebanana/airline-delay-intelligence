# Denver 2023–2025 weather extension

**Status:** Approved technical delta and three implementation slices, 2026-11-09.
**Requirements:** [Scope amendment](../prds/den-weather-2023-2025.md).
**Baseline:** Application `a962b2b4b2904e2310d3b81798fa8bc13409911e`;
flight release `02d263d7f7174890b6da97c15a81d098`.
**Supersedes:** Parent specification D07's January-only scope for this extension.

## Contract

- DEN scheduled source rows for 2023-01-01 through 2025-12-31: census 930,445,
  including 10,389 cancellations and 2,609 diversions. No new flight ingestion.
- NOAA GHCNh station candidate USW00003017, DENVER INTL AP, WMO 72565. Verify
  historical airport sequences 1129202/1129203 rather than dropping later rows.
- Acquire explicit, checksummed 2023/2024/2025 PSV files and only the required
  early-2026 UTC boundary observations. Expected weather envelope is
  [2023-01-01T06:00Z, 2026-01-01T07:00Z), including initial one-hour lookback.
- Version the new source/mapping/time/QC contract; preserve ISD-v1 verification.
  Consult official GHCNh definitions: never reuse ISD quality codes or units by
  assumption. Preserve measurement qualifiers and per-variable report/source IDs.
  In particular, qualified visibility must not silently become an exact reading.
- Independent latest-accepted-at-or-before matching per variable, inclusive age
  0–3600s. Retain QC rejection/missing/stale provenance. Conflicting good ties fail.
- Pin America/Denver timezone rules. Ambiguous/nonexistent local clocks have no
  guessed UTC anchor: retain schedules and explicit unresolved-time status. Only
  classified time exceptions relax the zero-null-anchor pilot rule; other mapping
  or integrity errors fail closed. Do not infer actual cancellation times.
- Retain one row per DEN flight key, all schedules in coverage denominators,
  >=95% overall coverage for each variable, monthly/subgroup diagnostics, zero future
  matches and multiplication. Do not waive unexplained gaps to pass publication.
- Preserve existing primary metrics, condition bands where units permit, filters,
  released-only reader, immutable identity, frozen reconstruction and atomic switch.

## Approved implementation slices and acceptance

1. **Adapter/scope:** bounded streaming, explicit manifests/checksums, documented
   GHCNh field semantics, decoder/identity/time/bounds tests and legacy compatibility.
2. **Matching/release:** version-aware dbt/frozen validation, independent oracle,
   36-month reconciliation, exceptional-time/sequence handling, exact replay and
   failed-publication preservation. Explain January GHCNh-versus-ISD differences.
3. **UI/delivery:** manifest-backed full-period DEN scope and copy, same uncluttered
   layout/support warnings, explicit resource packaging. Offline tests, dbt parse,
   container checks and bounded browser acceptance. No automatic local viewer start.

## Operational gates

50,000,000 bytes total NOAA response bodies, inclusive of 4,916,250 bytes preflight
already read at approval. No new tools, infrastructure, identities or grants.
Existing preflight allowance remains <=600s live work / 0.1 additional observed
credits. Preserve cumulative ledger/history and the 0.5-credit recovery reserve.

Offline implementation/acquisition does not authorize warehouse writes, candidate
build, publication, deployment or additional live spending. Before that stage,
approve exact objects/actions, identity/path, elapsed/credit ceilings and rollback.
Prefer reuse of accepted flight data; disclose full-candidate rebuild costs if
required rather than bypassing release validation. Retain previous immutable release.

## Unresolved verification, not assumed facts

Interior monthly variable/QC coverage, GHCNh quality/measurement interpretation,
historical sequence mapping evidence, bounded 2026 retrieval, artifact sizes and
measured live execution cost. Resolve from official sources/tests; stop on a genuine
coverage failure or a needed scope/spending change, not routine conservative fixes.
