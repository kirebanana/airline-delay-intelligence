# January 2025: ISD to GHCNh reconciliation

**Status:** Completed offline from checksum-verified held inputs, 2026-11-10.
Scope: all 24,732 scheduled DEN departures, including 313 cancelled and 69 diverted.
No flight rows, outcomes or primary flight metrics changed.

## Method and identities

The accepted January flight gzip was independently checked against its preparation
manifest. Each original source row was matched separately for temperature, wind and
visibility against both complete normalized observation artifacts. The comparison
implements its own sorted timestamp/binary-search backward matcher, not the production
SQL or publication oracle. The age limit is inclusive 0–3,600 seconds. January's
ordinary scheduled clocks are combined with America/Denver; no DST fold is inferred.

Old ISD weather identity:
`07c14d564d822fe812a562d35fe017aed3fd46aa16b66189ad69e0252b1614df`.
New GHCNh identity:
`b09c9b959da0a56b81638be8855f577af685db8d6849097dc952d8a9a4f6a167`.
Both payload hashes were checked before comparison. New payload identity was also
reconstructed from the four pinned original NOAA bodies, not inferred from a
self-signed prepared manifest. See [source semantics](specifications/den-ghcnh-source-semantics.md).

## Exact flight-level results

| Variable | ISD matched | GHCNh matched | Gained | Lost | Observation time changed | Band changed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Temperature | 24,585 | 24,732 | 147 | 0 | 153 | 147 |
| Wind | 24,683 | 24,732 | 49 | 0 | 50 | 49 |
| Visibility | 24,380 | 24,424 | 49 | 5 | 97 | 84 |

Time/value/band differences include transitions from/to unmatched, not just pairs
that matched in both sources. Every remaining flight-variable pair was checked too.

- **Temperature:** 98 gained matches use a timestamp present but rejected by the
  ISD quality policy; 49 use a newly available accepted report. Six existing matches
  select a newer accepted report. The 147 band changes are exactly 98 unmatched
  to at/above 0°C and 49 unmatched to −10–<0°C. No other temperature band changed.
- **Wind:** 49 gained reports change unmatched to <5m/s. One existing match selects
  a newer report with the same value. No already-matched wind band changed.
- **Visibility:** 49 gained reports change unmatched to ≥5,000m; five old matches
  in 1,600–<5,000m have no accepted replacement within an hour. Forty-two flights
  select older accepted observations under the source-specific rules: 30 move from
  402m to 2,414m, 11 from 0m to 201m, and one from 0m to 402m. One selects a newer
  report with unchanged value. Of 553 strict numeric-value differences, **457 are
  floating-point unit-conversion noise**, not different reported weather:
  415 values are 8,047 versus 8,047.000000000001m, and 42 are 4,023 versus
  4,022.9999999999995m. Those pairs never change bands. The remaining 96 value
  differences are the gained/lost/older-report cases above.

The two datasets and their source-specific acceptance policies differ; these are
not flight-data corrections. The evidence establishes exact match/time/value/band
effects, not why NOAA revised each underlying report. It does not assert the new
observations are meteorologically more accurate or that weather caused a disruption.

## Audit artifact

An ignored per-flight CSV records original source ordinal, date/clock, variable,
both observation times/values/bands and a deterministic difference classification.
Its SHA256 is `bd3f8a0c71346a88386148aa048eb3173553aa38f6d215de362db3121206a737`.
Full aggregates include every band transition, not only changed examples. No raw
flight rows or workstation paths are committed. This completes the previously
deferred January comparison; it is offline evidence, not a new warehouse query.
