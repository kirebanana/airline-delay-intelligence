# DEN scheduled-weather pilot

Implemented for **Denver-local January 2025**, not national weather or the final
36-month release. The preserved January NOAA extract is supplemented only with
Feb 1 00:00–06:59:59Z. Newly acquired observations are 12,697 bytes. NOAA's format
PDF and station-history reference were also preserved/checksummed (total new
acquisition ~4.1 MB); no annual weather or another flight month was downloaded.

## Contracts and lineage

`references/den-weather-pilot.json` records the scoped crosswalk and source
evidence. Contemporaneous BTS DEN/11292/1129202 and NOAA KDEN/name/location agree;
NOAA history records station 725650/03017 from 1994-07-18 to 2025-08-27. This is
airport-level January context, not a sensor relocation history or multi-year map.
The artifact binds that mapping and the local America/Denver TZif SHA-256.
Every published scheduled UTC anchor is independently checked against those
timezone rules. New midnight ambiguity fails rather than assuming a rollover.

Only FM-15/FM-16 aviation reports enter matching. Repeated CSV headers must agree;
padded call signs are stripped for identity comparison, not in preserved source.
Temperature is signed tenths °C; wind speed tenths m/s; visibility metres. Numeric
sentinels and field QC are decoded separately; only QC 1/5 is accepted, following
the preserved NOAA format. Identical accepted station/time/variable ties collapse
with all source-row provenance; conflicting accepted values fail closed.

Python handles the bounded source representation and provenance. dbt's
`weather_observations` and `den_weather` implement the reusable temporal join and
bands. Each variable independently selects the latest accepted prior observation,
inclusive ages 0–3600 seconds. Newest-report status and older-good fallback remain
visible. Raw files, original field encodings, observation age/time, source hashes,
mapping/time provenance and unmatched rows remain available. No compound conditions.

The release snapshots both weather tables alongside flights/dimensions. Frozen
validation checks the full weather-input checksum, reconstructs all decoded fields
and matches, compares every anchor to pinned timezone interpretation, and enforces
the full-population coverage gate before selection. Released views refer only to
their own frozen schema. Dependency identity includes fixed weather/mapping/time
versions; a complete active release cannot silently downgrade to flight-only.

## Independent full-window evidence

All **24,732** scheduled DEN rows are retained, including **313 cancellations**,
**69 diversions** and all **261 February-UTC anchors**. Independent original-file
matching agrees exactly with all three modelled observation times, ages and values
on every row; zero future matches or multiplication.

| Variable | Matched / all scheduled | Coverage |
|---|---:|---:|
| Temperature |24,585 /24,732|99.41%|
| Wind |24,683 /24,732|99.80%|
| Visibility |24,380 /24,732|98.58%|

Real SQL fixtures exercise age 0/3600/3601, future-only observations, independent
variable times and newer-rejected/older-good fallback. The dashboard shows full
pilot and separately filtered coverage, cancellation subgroups, missing/QC/stale
diagnostics, separate-variable comparisons, date support and largest-date share.
These are descriptive associations: shared episodes, schedule/route/carrier mix,
cancellation selection and observation availability prevent causal interpretation.

## Explicit commands

From the project repository, using the already installed locked environment:

```bash
airline prepare-weather --source /private/january.csv <sha256> \
  --source /private/february-boundary.csv <sha256> --output /private/new-weather
airline refresh --artifact /private/january-artifact --weather /private/new-weather \
  --output /private/new-attempt --budget-state /private/continuation-budget.json \
  --target january --request-id <32-lowercase-hex> --funding-verified
```

These commands do not download, upload to S3 or schedule work. The small weather
input is loaded through the existing builder identity; future cloud storage/job
integration remains subject to the later platform tickets. Do not opt into
`AIRLINE_WEATHER_LIVE=funded-12` without current funding and bounded test approval.
Full project acceptance, historical DST/national mapping, precipitation/ceiling,
predictions and significant weather effects are not claimed by this pilot.

## Published January milestone — 2026-10-30

The ordinary refresh publish-stage rerun selected the complete combined January
release after frozen validation. Real restricted-reader AppTest renders primary
KPIs, categories/recovery and DEN weather, including DEN filter/reset. Initial
cold/warm whole-render measurements are 20.91/5.21 seconds; no warehouse resizing.
Three live weather cases pass, including failed required-weather preservation.
Offline discovery executes 30 cases and skips 24 separately funded live cases;
Ruff and dbt parse pass. This is still a January milestone, not final acceptance.
