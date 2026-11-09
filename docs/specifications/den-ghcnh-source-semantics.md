# DEN GHCNh v2 source semantics and offline evidence

**Status:** Issue #13 implementation evidence, 2026-11-09; not warehouse publication
approval. Implements [the approved extension](den-weather-2023-2025.md).

## Primary evidence and identity

NOAA's [GHCNh documentation](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf),
v1.1.0, updated 2026-03-10, was acquired in full (423,879 bytes), SHA256
`df5694efdc2d498f006a343165bae65701d14809174b9bed660149bd4fe591b7`.
Sections III–VII, pages 6–15, define fields, units, measurement codes, source-specific
quality codes and report types. Section XI delegates full source descriptions to
a separate source-list PDF; that PDF was **not** acquired. No undocumented source
code is accepted by this adapter. The PDF was extracted offline using its embedded
ToUnicode maps and Flate streams; no tools were installed.

[The versioned mapping resource](../../references/den-ghcnh-weather-v2.json) pins
station USW00003017, WMO72565, DENVER INTL AP, coordinates 39.8467/-104.6561,
source identities/checksums/HTTP validators, documentation hash, timezone TZif hash,
and scope. The source is airport-level weather context, not proof of runway
conditions or unchanged sensor locations. NOAA says station-list coordinates come
from source-provider inventories; they are not a relocation history.

Accepted BTS release `02d263d7f7174890b6da97c15a81d098` preflight evidence records
origin ID 11292 with sequence 1129202 through June 2025 and 1129203 in July–December
2025. Thus the January sequence must not be used to drop later schedules. This is
available source-row evidence, not an independently acquired BTS airport-history
crosswalk; no additional flight month or cloud query was performed here.

## Exact acceptance policy

Contract: `den-ghcnh-aviation-independent-60m-v2`. Each variable uses its own five
attribute columns; a row's temperature source/report never stands in for wind or
visibility's source/report. FM15 is routine METAR; FM16 is SPECI. FM12 SYNOP and
all other report types remain rejected observations, not accepted substitutes.

| Variable | Input unit | Prepared unit | Accepted measurement semantics |
|---|---|---|---|
| temperature | decimal degrees C | degrees C | blank measurement code; no ISD /10 scaling |
| wind_speed → wind | decimal m/s | m/s | N normal, V variable direction, C calm only with zero speed; not gusts or longer-period averages |
| visibility | decimal km | meters (×1000) | source 343 N = not variable; source 223 P = prevailing; other codes rejected |

The main documentation explicitly says visibility **P means prevailing for
source 223** (page 10), not “plus”, “greater than”, or a lower bound. Blanket
rejection of P would incorrectly discard most late-2025 observations. Nevertheless,
METAR `P6SM`/`M1/4SM` qualifiers are not exact values: either in the main raw REM
section causes `qualified_visibility`, with null numeric value. Raw REM and all
its source attributes are preserved. Qualifiers in the RMK section describe
secondary observations rather than the selected main observation. Variable
visibility (343 V), aircraft/slant/minimum/maximum/sector visibility and unknown
measurement codes are conservatively rejected. No censored value becomes an exact
reading or an invented condition band.

The complete annual files demonstrate two source-station encodings for KDEN:

* Source **343**, station **725650-03017** (the historical WMO/WBAN identity), is
  corroborated by original REM METAR/SPECI KDEN reports. Its documented legacy QC
  **1** and **5** mean passed all checks; **A** means flagged suspect but accepted
  as good. A is accepted deliberately with its original flag retained, not because
  of an ISD whitelist. Other flags, including gross-check-only 0/4/9, edited or
  replaced P/U, suspect 2/6 and erroneous 3/7, are not accepted.
* Source **223**, station **ICAO-KDEN**, accepts QC **1** (good) only. For this
  source, **5 means removed**, not good. QC 0 is unchecked; 2 suspect; 3 erroneous;
  4 calculated. None is accepted.
* Source **999** (present during 2025) has no documented acceptance rule in the
  acquired primary documentation and generally blank QC. It is rejected; its
  FM15/FM16 spelling does not make it trusted. Global lowercase QC failure flags,
  combinations and unknown codes are rejected, not stripped before comparison.

Rejecting every legacy 343 station string in favor of a literal ICAO-KDEN-only
comparison would remove most 2023–early-2025 measurements. Both explicit source
station mappings refer to the same airport identity; mismatches for either known
source raise rather than silently creating coverage gaps. Nonfinite values,
syntactically malformed decimals, impossible conservative safety bounds, missing
values and missing attributes cannot be accepted. Safety ranges are adapter
integrity guards, not claims that NOAA defines those physical extrema.

## Bounded acquisition and preservation

All downloaded bodies and exact cumulative accounting live in outer ignored
`.scratch/airline-delay-intelligence/den-weather-2023-2025/acquisition/`.
`ledger.json` includes the approved 4,916,250-byte prior-probe baseline and every
new response body. No automatic retries, annual-2026 fallback or repeat successful
downloads were used. Annual PSV bodies are preserved byte-for-byte.

| Body | Bytes |
|---|---:|
| Prior probes | 4,916,250 |
| Documentation PDF | 423,879 |
| 2023 annual PSV | 13,143,457 |
| 2024 annual PSV | 12,401,545 |
| 2025 annual PSV | 12,069,776 |
| 2026 initial range, bytes 0–32767 | 32,768 |
| **Total consumed / approved cap** | **42,987,675 / 50,000,000** |

2026 returned HTTP 206, Content-Range `bytes 0-32767/40563877`; ETag and
Last-Modified are pinned in the resource and ledger. The raw prefix reaches
12:50Z on January 1, sufficient to prove the [00:00Z,07:00Z) boundary is included.
Only the final incomplete record is excluded from parsing; raw bytes remain
preserved: 32,494 complete-record bytes, 274 trailing partial bytes. The prepared
manifest records raw SHA/size, complete-record SHA/size,
discarded-tail count and validators. No full 40,563,877-byte 2026 body was read.

Parser bounds: 65,536 characters/line, 100,000 source rows/file, 128 reports/time,
14 MB/file maximum (2026 <=32,768 bytes), 40 MB cumulative weather input,
160,000 output rows, 200 MB prepared payload. Annual lengths and all four acquired
checksums are pinned. Inputs must be UTC-monotonic, have unique required headers,
exact widths and the fixed station/coordinates. Equal-time accepted conflicts
raise; identical accepted ties collapse with all provenance retained. Grouping
is bounded to one timestamp, not the full multi-year dataset. Cross-file duplicate
or unordered keys fail. Source digests are checked before and after parsing.

## Adapter and integration interface

`airline_warehouse.ghcnh` exports:

* `prepare_ghcnh(sources, output)` — four `(Path, expected_sha256)` pairs, one each
  2023/2024/2025 annual and 2026 prefix. Paths use the acquired NOAA basenames
  (2026 may end `.prefix.psv`). No acquisition or warehouse calls. Create-only
  output contains `manifest.json` and `observations.jsonl`.
* `parse_observations(text_stream, source_sha, *, year=None)` — bounded iterator
  of unique observations. Caller must supply complete records, not a raw partial
  byte range. `decode(variable, raw_row)` is independently testable.
* `read_ghcnh(path)` — checked `(manifest, JSONL_string_rows)`, matching the legacy
  reader's return shape. `MAX_ROWS` replaces the v1 10,000-row bound for v2.

Observation core keys remain `station`, `observed_at`, `variable`, `value`,
`status`, `duplicate_count`, `provenance`. Values exist only for accepted records.
Provenance includes original raw value, per-variable measurement/QC/report/source
attributes, source SHA/row ordinal, REM and REM attributes. Nonaccepted rows remain
available for missing/QC/stale diagnostics. Canonical order is observed_at/variable.

Manifest includes contract, explicit local scope_start/scope_end_exclusive,
UTC start/end, station, origin_id, origin_sequences, mapping_version/mapping_sha256,
timezone/timezone_sha256, source identities, rows, payload_bytes/payload_sha256 and
weather_id. Weather ID uses the legacy SHA256 of sorted-key JSON identity convention.

`airline_warehouse.weather_contract` exports:

* `contract_scope(manifest)` — canonical dictionary with local scope, UTC bounds,
  station and origin_id; accepts legacy January v1 without new local-scope fields,
  rejects unknown contracts and contradictory bounds.
* `mapping_sha256()`, `reference()`, `verify_mapping(manifest)` — resource access
  and strict v2 dependency checks; verification returns the canonical scope.
* `classify_scheduled_anchor(date, clock, manifest)` — `(UTC datetime | None,
  status)`. Status is resolved, ambiguous_local_time, nonexistent_local_time or
  unresolved_midnight. Invalid clocks/dates/mapping are integrity errors, not
  waivers. `scheduled_anchor(date, clock, manifest)` returns just the nullable UTC
  datetime. Legacy calls delegate to the untouched January implementation.

America/Denver rules are pinned by TZif SHA and loaded from those same verified
bytes. Both folds undergo UTC roundtrip: two valid candidates means ambiguous;
none means nonexistent. Neither chooses a fold. 0000/2400 remain explicitly
unresolved, not guessed rollover. Retain all such flight rows in denominators.
The one evidenced 2023-11-05 01:19 schedule is unmatchable by construction.

Integration must dispatch v2 reading/loading/frozen validation separately, use
the v2 row bound and helpers, and retain independent latest-accepted matching with
inclusive 0–3600s age. No existing weather/dbt/dashboard file is changed here.
Resource packaging remains the integration/UI slice's responsibility.

## Offline whole-source diagnostics (not flight acceptance)

Reading the acquired four inputs produces **120,708** canonical observation rows;
exact canonical JSON serialization estimates **83,671,259 bytes**. No prepared
full artifact or warehouse candidate was built. A minute-resolution UTC anchor
grid over the Denver-local scope, using only accepted observations and the
inclusive backward hour, has overall eligibility **99.456% temperature,
99.452% wind, 99.317% visibility**. This is a weather-only diagnostic, **not** a
flight-weighted coverage result or publication gate. Actual schedules, cancellation/
diversion subgroups and ambiguous anchors still require the independent integration
oracle and all-row reconciliation.

In the table, counts are accepted UTC-month reports (T/W/V); eligibility is a
Denver-local-month minute-grid diagnostic (T/W/V). Different month definitions are
intentional and must not be mistaken for one denominator.

| Month | Accepted T / W / V reports | Minute-grid eligibility T / W / V |
|---|---|---|
| 2023-01 | 1001 / 1001 / 984 | 100.00% / 100.00% / 99.30% |
| 2023-02 | 763 / 763 / 761 | 100.00% / 100.00% / 100.00% |
| 2023-03 | 980 / 979 / 976 | 100.00% / 99.98% / 100.00% |
| 2023-04 | 917 / 913 / 917 | 100.00% / 99.99% / 100.00% |
| 2023-05 | 1016 / 1014 / 1014 | 100.00% / 99.99% / 100.00% |
| 2023-06 | 989 / 987 / 989 | 100.00% / 100.00% / 100.00% |
| 2023-07 | 974 / 970 / 973 | 100.00% / 99.97% / 100.00% |
| 2023-08 | 879 / 876 / 879 | 100.00% / 99.98% / 100.00% |
| 2023-09 | 818 / 815 / 818 | 99.99% / 99.97% / 99.99% |
| 2023-10 | 884 / 883 / 880 | 99.99% / 99.98% / 99.99% |
| 2023-11 | 812 / 811 / 811 | 100.00% / 99.99% / 99.97% |
| 2023-12 | 864 / 864 / 861 | 100.00% / 100.00% / 100.00% |
| 2024-01 | 863 / 862 / 863 | 100.00% / 99.99% / 100.00% |
| 2024-02 | 943 / 943 / 935 | 100.00% / 100.00% / 99.87% |
| 2024-03 | 932 / 931 / 931 | 99.73% / 99.73% / 99.70% |
| 2024-04 | 950 / 947 / 945 | 100.00% / 99.97% / 100.00% |
| 2024-05 | 841 / 840 / 841 | 100.00% / 99.87% / 100.00% |
| 2024-06 | 807 / 805 / 807 | 100.00% / 99.72% / 100.00% |
| 2024-07 | 819 / 819 / 819 | 100.00% / 100.00% / 100.00% |
| 2024-08 | 890 / 889 / 888 | 100.00% / 99.99% / 100.00% |
| 2024-09 | 775 / 774 / 774 | 100.00% / 99.94% / 99.94% |
| 2024-10 | 790 / 790 / 790 | 100.00% / 100.00% / 100.00% |
| 2024-11 | 914 / 914 / 870 | 100.00% / 100.00% / 98.07% |
| 2024-12 | 754 / 755 / 755 | 100.00% / 100.00% / 100.00% |
| 2025-01 | 993 / 992 / 965 | 100.00% / 100.00% / 99.14% |
| 2025-02 | 850 / 852 / 831 | 99.85% / 100.00% / 99.38% |
| 2025-03 | 883 / 884 / 880 | 100.00% / 100.00% / 99.77% |
| 2025-04 | 928 / 930 / 924 | 100.00% / 100.00% / 99.72% |
| 2025-05 | 960 / 961 / 952 | 100.00% / 100.00% / 99.66% |
| 2025-06 | 871 / 874 / 868 | 99.86% / 99.97% / 99.52% |
| 2025-07 | 887 / 887 / 890 | 100.00% / 99.92% / 100.00% |
| 2025-08 | 801 / 800 / 793 | **89.64% / 89.58% / 89.59%** |
| 2025-09 | 727 / 727 / 727 | **92.67% / 92.67% / 92.67%** |
| 2025-10 | 771 / 771 / 771 | 99.47% / 99.47% / 99.47% |
| 2025-11 | 765 / 766 / 766 | 99.59% / 99.73% / 99.73% |
| 2025-12 | 820 / 823 / 823 | 99.72% / 100.00% / 100.00% |

August/September 2025 gaps are real under the documented acceptance policy,
including rejection of QC-unknown source 999. They must be disclosed and explained,
not “fixed” by trusting undocumented source/QC or accepting SYNOP reports. The
approved numeric threshold is >=95% **overall** per variable, with monthly/subgroup
diagnostics; no monthly threshold waiver is implied. Qualified visibility rejects
31 in-envelope reports across the inputs. A direct January GHCNh-versus-ISD flight
comparison belongs to the matching/release slice; source scaling, source-specific
QC, retained censoring, accepted-good A, and independent report selection explain
why identical January values or counts are not assumed.

Offline fixtures cover units, per-variable report independence, source-specific
QC (especially 223 QC5), measurement codes, qualified visibility, invalid identity,
UTC bounds, duplicate preservation/conflicts, stream bounds/truncation/order,
create-only artifacts, deterministic replay/tampering, legacy scope and DST gap/fold
classification. No source download occurs in tests.
