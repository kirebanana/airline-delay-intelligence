"""Offline, bounded GHCNh PSV adapter. Acquisition is deliberately not automatic.

prepare_ghcnh([(path, expected_sha256), ...], output) writes the same core
observation schema as ISD, with independent per-variable source provenance.
"""

import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import tempfile
from pathlib import Path

from airline_warehouse.weather_contract import (
    CONTRACT as CONTRACT,
)
from airline_warehouse.weather_contract import (
    mapping_sha256,
    reference,
    verify_mapping,
)

STATION = "USW00003017"
START = dt.datetime(2023, 1, 1, 6, tzinfo=dt.UTC)
END = dt.datetime(2026, 1, 1, 7, tzinfo=dt.UTC)
VARIABLES = {"temperature": "temperature", "wind": "wind_speed", "visibility": "visibility"}
ATTRIBUTES = ("Measurement_Code", "Quality_Code", "Report_Type", "Source_Code", "Source_Station_ID")
MAX_LINE = 65536
MAX_SOURCE_ROWS = 100000
MAX_ROWS = 160000
MAX_PAYLOAD_BYTES = 200_000_000
MAX_SOURCE_BYTES = 14_000_000
MAX_TOTAL_BYTES = 40_000_000
MAX_REPORTS_PER_TIME = 128
BASE_URL = (
    "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/by-year"
)
SOURCE_SIZES = {2023: 13143457, 2024: 12401545, 2025: 12069776, 2026: 32768}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode(variable, row):
    """Return (value in C / m/s / meters, status); never infer missing/QC.

    GHCNh decimal values are already scaled. QC meaning depends on source.
    P for source 223 visibility means *prevailing*, NOT 'greater than'.
    Explicit METAR P/M...SM bounds are conservatively unmatchable.
    """
    field = VARIABLES[variable]
    raw = row[field]
    source = row[field + "_Source_Code"]
    if not raw or raw == "-9999":
        return None, "missing"
    if row[field + "_Report_Type"] not in ("FM15", "FM16"):
        return None, "rejected_report_type"
    ref = reference()
    if source not in ref["source_stations"]:
        return None, "rejected_source"
    if row[field + "_Source_Station_ID"] != ref["source_stations"][source]:
        raise ValueError("GHCNh aviation source station mapping mismatch")
    if row[field + "_Quality_Code"] not in ref["quality_acceptance"][source]:
        return None, "rejected_qc"
    if not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", raw):
        return None, "malformed"
    value = float(raw)
    bounds = {"temperature": (-100, 70), "wind": (0, 100), "visibility": (0, 160)}
    if not math.isfinite(value) or not bounds[variable][0] <= value <= bounds[variable][1]:
        return None, "malformed"
    code = row[field + "_Measurement_Code"]
    if variable == "temperature" and code != "":
        return None, "rejected_measurement"
    if variable == "wind" and (code not in ("N", "C", "V") or (code == "C" and value != 0)):
        return None, "rejected_measurement"
    if variable == "visibility":
        if code != {"343": "N", "223": "P"}[source]:
            return None, "rejected_measurement"
        # Raw report may preserve censoring not represented in measurement code.
        # Restrict to the main METAR section: RMK can contain secondary visibilities.
        remarks = row.get("REM", "").split(" RMK", 1)[0]
        if re.search(r"(?<![A-Z0-9])[PM][0-9]+(?:/[0-9]+)?SM\b", remarks):
            return None, "qualified_visibility"
        value *= 1000  # GHCNh kilometers -> existing condition-band meters.
    return value, "accepted"


def _lines(stream):
    while line := stream.readline(MAX_LINE + 1):
        if len(line) > MAX_LINE or not line.endswith("\n"):
            raise ValueError("GHCNh oversized or incomplete record")
        yield line


def _resolve(stamp, reports):
    for variable, provenance in sorted(reports.items()):
        good = {r["value"] for r in provenance if r["status"] == "accepted"}
        if len(good) > 1:
            raise ValueError("Conflicting accepted station/time/variable measurements")
        chosen = next((r for r in provenance if r["status"] == "accepted"), provenance[0])
        yield {
            "station": STATION,
            "observed_at": stamp.isoformat(),
            "variable": variable,
            "value": chosen["value"],
            "status": chosen["status"],
            "duplicate_count": len(provenance),
            "provenance": provenance,
        }


def parse_observations(stream, source_sha, *, year=None):
    """Yield sorted unique time/variable records, retaining only one time group.

    Monotonic UTC input, fixed station/location, explicit row widths, unique
    headers, per-file record limits and duplicate-group limits fail closed.
    Pass a complete-record stream (truncate range response separately).
    """
    reader = csv.reader(_lines(stream), delimiter="|", quoting=csv.QUOTE_NONE)
    header = next(reader, [])
    required = {"STATION", "DATE", "LATITUDE", "LONGITUDE", "REM"}
    required.update(VARIABLES.values())
    required.update(f"{field}_{attr}" for field in VARIABLES.values() for attr in ATTRIBUTES)
    if len(header) != len(set(header)) or not required <= set(header):
        raise ValueError("Missing/duplicate GHCNh header")
    previous, reports, group_count = None, {}, 0
    for ordinal, cells in enumerate(reader, 1):
        if ordinal > MAX_SOURCE_ROWS or len(cells) != len(header):
            raise ValueError("GHCNh row width/count exceeds contract")
        row = dict(zip(header, cells, strict=True))
        if (
            row["STATION"] != STATION
            or row["LATITUDE"] != "39.8467"
            or row["LONGITUDE"] != "-104.6561"
        ):
            raise ValueError("Unexpected GHCNh station/location")
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:00", row["DATE"]):
            raise ValueError("Malformed GHCNh UTC timestamp")
        stamp = dt.datetime.fromisoformat(row["DATE"]).replace(tzinfo=dt.UTC)
        if year is not None and stamp.year != year:
            raise ValueError("GHCNh source year mismatch")
        if previous is not None and stamp < previous:
            raise ValueError("Unordered GHCNh timestamps")
        if stamp != previous:
            if reports:
                yield from _resolve(previous, reports)
            reports, group_count = {}, 0
        previous = stamp
        group_count += 1
        if group_count > MAX_REPORTS_PER_TIME:
            raise ValueError("Excessive duplicate GHCNh reports")
        if not START <= stamp < END:
            continue
        for variable, field in VARIABLES.items():
            value, status = decode(variable, row)
            provenance = {
                "value": value,
                "status": status,
                "raw": row[field],
                "source_sha256": source_sha,
                "source_row": ordinal,
                "report_type": row[field + "_Report_Type"],
                "measurement_code": row[field + "_Measurement_Code"],
                "quality_code": row[field + "_Quality_Code"],
                "source_code": row[field + "_Source_Code"],
                "source_station_id": row[field + "_Source_Station_ID"],
                "remarks": row["REM"],
                "remarks_attributes": {a: row.get("REM_" + a, "") for a in ATTRIBUTES},
            }
            reports.setdefault(variable, []).append(provenance)
    if reports:
        yield from _resolve(previous, reports)


def _source_identity(path, expected):
    path = Path(path)
    match = re.fullmatch(r"GHCNh_USW00003017_(202[3-6])(?:\.prefix)?\.psv", path.name)
    if not match or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("Explicit approved GHCNh source identity required")
    year = int(match[1])
    pinned = reference()["source_objects"][str(year)]
    if expected != pinned["sha256"]:
        raise ValueError("GHCNh source checksum is not the pinned acquisition")
    size = path.stat().st_size
    if not 0 < size <= min(MAX_SOURCE_BYTES, SOURCE_SIZES[year]):
        raise ValueError("GHCNh input byte bound exceeded")
    if year < 2026 and size != SOURCE_SIZES[year]:
        raise ValueError("GHCNh annual input is incomplete or changed")
    if _sha(path) != expected:
        raise ValueError("GHCNh source checksum mismatch")
    identity = {
        "year": year,
        "url": f"{BASE_URL}/{year}/psv/GHCNh_USW00003017_{year}.psv",
        "sha256": expected,
        "bytes": size,
        "kind": "initial_byte_range" if year == 2026 else "annual_psv",
        "validators": {key: value for key, value in pinned.items() if key != "sha256"},
    }
    return identity


def prepare_ghcnh(sources, output):
    """Create-only artifact from four explicit (path, SHA256) inputs, no network.

    Annual inputs retain all original bytes; 2026 is an initial <=32768-byte
    range. Only its final incomplete line is ignored and its truncation is
    hashed/count-recorded. Caller preserves originals and acquisition validators.
    """
    output = Path(output)
    sources = list(sources)
    if output.exists() or len(sources) != 4:
        raise ValueError("GHCNh requires create-only output and four bounded imports")
    identities = [_source_identity(path, sha) for path, sha in sources]
    if sorted(i["year"] for i in identities) != [2023, 2024, 2025, 2026]:
        raise ValueError("GHCNh requires each annual input and boundary exactly once")
    if sum(i["bytes"] for i in identities) > MAX_TOTAL_BYTES:
        raise ValueError("GHCNh cumulative source bound exceeded")
    ref = reference()
    manifest = {
        key: ref[key]
        for key in (
            "contract",
            "scope_start",
            "scope_end_exclusive",
            "start",
            "end",
            "station",
            "origin_id",
            "origin_sequences",
            "timezone",
            "timezone_sha256",
        )
    }
    manifest.update(mapping_version=ref["version"], mapping_sha256=mapping_sha256())
    verify_mapping(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Temporary output is local-only and cleaned on failure; previous artifact untouched.
    with tempfile.TemporaryDirectory(prefix=".ghcnh-", dir=output.parent) as temporary:
        payload = Path(temporary) / "observations.jsonl"
        digest = hashlib.sha256()
        count, payload_bytes, previous = 0, 0, None
        with payload.open("wb") as target:
            for (path, sha), identity in sorted(
                zip(sources, identities, strict=True), key=lambda pair: pair[1]["year"]
            ):
                path = Path(path)
                if identity["year"] == 2026:
                    raw = path.read_bytes()  # hard bounded to 32768 above
                    complete = raw[: raw.rfind(b"\n") + 1]
                    identity.update(
                        complete_record_bytes=len(complete),
                        complete_record_sha256=hashlib.sha256(complete).hexdigest(),
                        discarded_partial_bytes=len(raw) - len(complete),
                    )
                    stream = io.StringIO(complete.decode("utf-8"))
                    # A record after the selection end proves the prefix covers the boundary.
                    dates = [r["DATE"] for r in csv.DictReader(stream, delimiter="|")]
                    if not dates or dates[-1] < "2026-01-01T07:00:00":
                        raise ValueError("GHCNh prefix does not cover UTC boundary")
                    stream.seek(0)
                else:
                    stream = path.open(encoding="utf-8", newline="")
                with stream:
                    for row in parse_observations(stream, sha, year=identity["year"]):
                        key = row["observed_at"], row["variable"]
                        if previous is not None and key <= previous:
                            raise ValueError("Overlapping/duplicate weather inputs")
                        previous = key
                        encoded = (_json(row) + "\n").encode()
                        count += 1
                        payload_bytes += len(encoded)
                        if count > MAX_ROWS or payload_bytes > MAX_PAYLOAD_BYTES:
                            raise ValueError("GHCNh artifact exceeds bounds")
                        target.write(encoded)
                        digest.update(encoded)
                # Detect sources changed during parsing, not merely before it.
                if _sha(path) != sha:
                    raise ValueError("GHCNh source changed during preparation")
        if not count:
            raise ValueError("Empty GHCNh artifact")
        manifest.update(
            sources=sorted(identities, key=lambda i: i["year"]),
            rows=count,
            payload_sha256=digest.hexdigest(),
            payload_bytes=payload_bytes,
        )
        manifest["weather_id"] = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest()
        (Path(temporary) / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        # mkdir rather than replace enforces create-only even if another writer raced.
        output.mkdir()
        for name in ("observations.jsonl", "manifest.json"):
            (Path(temporary) / name).rename(output / name)
    return manifest


def read_ghcnh(path):
    """Verify immutable artifact; return (manifest, JSONL string rows), like v1."""
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    from airline_warehouse.weather_trust import verify_trusted_weather

    verify_trusted_weather(manifest)
    verify_mapping(manifest)
    sources = manifest.get("sources", [])
    if len(sources) != 4 or [s.get("year") for s in sources] != [2023, 2024, 2025, 2026]:
        raise ValueError("GHCNh manifest source set mismatch")
    for source in sources:
        year = source["year"]
        pinned = reference()["source_objects"][str(year)]
        if (
            source.get("sha256") != pinned["sha256"]
            or source.get("url") != f"{BASE_URL}/{year}/psv/GHCNh_USW00003017_{year}.psv"
            or source.get("validators") != {k: v for k, v in pinned.items() if k != "sha256"}
            or not 0 < source.get("bytes", 0) <= SOURCE_SIZES[year]
            or (year < 2026 and source["bytes"] != SOURCE_SIZES[year])
        ):
            raise ValueError("GHCNh manifest source identity mismatch")
    identity = {key: value for key, value in manifest.items() if key != "weather_id"}
    if hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest() != manifest.get(
        "weather_id"
    ):
        raise ValueError("GHCNh manifest identity mismatch")
    payload = path / "observations.jsonl"
    if (
        not 0 < manifest["rows"] <= MAX_ROWS
        or not 0 < payload.stat().st_size <= MAX_PAYLOAD_BYTES
        or payload.stat().st_size != manifest["payload_bytes"]
        or _sha(payload) != manifest["payload_sha256"]
    ):
        raise ValueError("GHCNh payload identity/size mismatch")
    with payload.open() as stream:
        rows = list(_lines(stream))
    if len(rows) != manifest["rows"]:
        raise ValueError("GHCNh row count mismatch")
    return manifest, [r.removesuffix("\n") for r in rows]
