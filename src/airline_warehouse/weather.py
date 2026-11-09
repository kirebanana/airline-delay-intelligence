"""Versioned DEN weather inputs, immutable loading and frozen-release verification.

Decoding/provenance belong here; variable-specific backward matching and reusable
analytical meaning belong in dbt. No automatic download or annual-file fallback.
"""

import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

STATION = "72565003017"
START = dt.datetime(2025, 1, 1, 6, tzinfo=dt.UTC)
END = dt.datetime(2025, 2, 1, 7, tzinfo=dt.UTC)
CONTRACT = "den-isd-aviation-qc15-independent-60m-v1"
GHCNH_CONTRACT = "den-ghcnh-aviation-independent-60m-v2"
VARIABLES = ("temperature", "wind", "visibility")
REFERENCE = Path(__file__).resolve().parents[2] / "references/den-weather-pilot.json"


def weather_scope(manifest):
    """Validated version dispatch. Never interpret v1 as the expanded population.

    The v2 adapter verifies mapping evidence and pinned timezone dependency.
    """
    if manifest.get("contract") == CONTRACT:
        from airline_warehouse.weather_contract import contract_scope

        canonical = contract_scope(manifest)
        if (manifest.get("start"), manifest.get("end")) != (START.isoformat(), END.isoformat()):
            raise ValueError("Incompatible legacy weather bounds")
        if (
            manifest.get("mapping_sha256") != hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
            or manifest.get("timezone_sha256")
            != hashlib.sha256(Path("/usr/share/zoneinfo/America/Denver").read_bytes()).hexdigest()
            or manifest.get("station") != STATION
            or manifest.get("origin_id") != 11292
            or manifest.get("origin_sequence") != "1129202"
            or manifest.get("timezone") != "America/Denver"
        ):
            raise ValueError("Incompatible legacy weather dependency")
        return {
            "start": canonical["scope_start"],
            "end": canonical["scope_end_exclusive"],
            "station": canonical["station"],
        }
    if manifest.get("contract") != GHCNH_CONTRACT:
        raise ValueError("Unknown weather contract")
    from airline_warehouse.weather_contract import verify_mapping

    verify_mapping(manifest)
    if (
        manifest.get("scope_start") != "2023-01-01"
        or manifest.get("scope_end_exclusive") != "2026-01-01"
        or manifest.get("station") != "USW00003017"
        or manifest.get("origin_id") != 11292
        or manifest.get("origin_sequences") != ["1129202", "1129203"]
        or manifest.get("timezone") != "America/Denver"
        or manifest.get("timezone_sha256")
        != hashlib.sha256(Path("/usr/share/zoneinfo/America/Denver").read_bytes()).hexdigest()
        or dt.datetime.fromisoformat(manifest["start"]) != dt.datetime(2023, 1, 1, 6, tzinfo=dt.UTC)
        or dt.datetime.fromisoformat(manifest["end"]) != dt.datetime(2026, 1, 1, 7, tzinfo=dt.UTC)
    ):
        raise ValueError("Incompatible expanded weather scope")
    return {
        "start": manifest["scope_start"],
        "end": manifest["scope_end_exclusive"],
        "station": manifest["station"],
    }


def weather_variables(manifest):
    scope = weather_scope(manifest)
    return {
        "weather_enabled": True,
        "weather_contract": manifest["contract"],
        "weather_scope_start": scope["start"],
        "weather_scope_end": scope["end"],
        "weather_station": scope["station"],
    }


def validate_weather_inputs(manifest, inputs):
    scope = weather_scope(manifest)
    required = {
        f"{year}-{month:02d}"
        for year in range(2023, 2026)
        for month in range(1, 13)
        if scope["start"][:7] <= f"{year}-{month:02d}" < scope["end"][:7]
    }
    if not required <= set(inputs):
        raise ValueError("Weather requires all selected flight months in its manifest scope")


def weather_limits(manifest):
    """v2 execution bounds are operator-selected from measured local artifacts.

    No implicit million-row ceiling or unbounded warehouse fetch. These positive
    limits must be part of the separately approved live execution environment.
    """
    if manifest.get("contract") == CONTRACT:
        return {"bytes": 20 * 1024 * 1024, "observations": 10000, "flights": 100000}
    limits = {}
    for key in ("bytes", "observations", "flights"):
        raw = os.environ.get("AIRLINE_WEATHER_MAX_" + key.upper(), "")
        if not re.fullmatch(r"[1-9][0-9]{0,11}", raw):
            raise ValueError("v2 requires measured AIRLINE_WEATHER_MAX_" + key.upper())
        limits[key] = int(raw)
    from airline_warehouse.ghcnh import MAX_PAYLOAD_BYTES, MAX_ROWS

    if (
        limits["bytes"] > MAX_PAYLOAD_BYTES
        or limits["observations"] > MAX_ROWS
        or limits["flights"] > 930445
    ):
        raise ValueError("Measured weather limits exceed the fixed adapter/census envelope")
    return limits


@lru_cache(maxsize=2)
def _pinned_zone(checksum):
    data = Path("/usr/share/zoneinfo/America/Denver").read_bytes()
    if hashlib.sha256(data).hexdigest() != checksum:
        raise ValueError("Pinned timezone changed")
    return ZoneInfo.from_file(io.BytesIO(data), key="America/Denver")


def classified_anchor(date, clock, manifest, *, _scope=None):
    """Independent round-trip timezone oracle; no fold or gap is guessed."""
    scope = _scope if _scope is not None else weather_scope(manifest)
    day = dt.date.fromisoformat(date)
    if not scope["start"] <= day.isoformat() < scope["end"]:
        raise ValueError("Scheduled date outside manifest scope")
    if manifest["contract"] == CONTRACT:
        return scheduled_anchor(date, clock), "resolved"
    if not re.fullmatch(r"[0-9]{1,4}", clock):
        raise ValueError("Malformed scheduled local clock")
    hour, minute = divmod(int(clock), 100)
    if (hour, minute) in ((0, 0), (24, 0)):
        return None, "unresolved_midnight"
    if hour > 23 or minute > 59 or (hour, minute) == (0, 0):
        raise ValueError("Unresolved midnight or malformed scheduled clock")
    naive = dt.datetime.combine(day, dt.time(hour, minute))
    zone = _pinned_zone(manifest["timezone_sha256"])
    candidates = set()
    for fold in (0, 1):
        utc = naive.replace(tzinfo=zone, fold=fold).astimezone(dt.UTC)
        if utc.astimezone(zone).replace(tzinfo=None) == naive:
            candidates.add(utc)
    if len(candidates) == 0:
        return None, "nonexistent_local_time"
    if len(candidates) == 2:
        return None, "ambiguous_local_time"
    return candidates.pop(), "resolved"


def scheduled_anchor(date, clock):
    """R06 snapshot rule: new midnight ambiguities require review, not rollover."""
    day = dt.date.fromisoformat(date)
    if not dt.date(2025, 1, 1) <= day < dt.date(2025, 2, 1):
        raise ValueError("Outside the fixed Denver-local January pilot")
    if not re.fullmatch(r"[0-9]{1,4}", clock):
        raise ValueError("Malformed scheduled local clock")
    hour, minute = divmod(int(clock), 100)
    if hour > 23 or minute > 59 or (hour, minute) == (0, 0):
        raise ValueError("Unresolved midnight or malformed scheduled clock")
    return dt.datetime.combine(day, dt.time(hour, minute), ZoneInfo("America/Denver")).astimezone(
        dt.UTC
    )


def decode(variable, raw):
    parts = raw.split(",")
    index, qc_index, size, sentinel, scale, low, high = {
        "temperature": (0, 1, 2, "+9999", 10, -932, 618),
        "wind": (3, 4, 5, "9999", 10, 0, 900),
        "visibility": (0, 1, 4, "999999", 1, 0, 160000),
    }[variable]
    pattern = {"temperature": r"[-+][0-9]{4}", "wind": r"[0-9]{4}", "visibility": r"[0-9]{6}"}[
        variable
    ]
    if len(parts) != size or not re.fullmatch(pattern, parts[index]):
        return None, "malformed"
    if parts[index] == sentinel:
        return None, "missing"
    value = int(parts[index])
    if not low <= value <= high:
        return None, "malformed"
    if parts[qc_index] not in {"1", "5"}:
        return None, "rejected_qc"
    return value / scale, "accepted"


def parse_observations(stream, source_sha):
    reader = csv.reader(stream)
    header = next(reader)
    required = {"STATION", "DATE", "REPORT_TYPE", "CALL_SIGN", "TMP", "WND", "VIS"}
    if not required <= set(header):
        raise ValueError("Missing required NOAA columns")
    grouped = {}
    for ordinal, cells in enumerate(reader, 1):
        if len(cells) != len(header):
            raise ValueError("NOAA row width mismatch")
        row = {}
        for name, value in zip(header, cells, strict=True):
            if name in row and row[name] != value:
                raise ValueError("Repeated NOAA header values disagree")
            row[name] = value
        if row["STATION"] != STATION:
            raise ValueError("Unexpected NOAA station")
        stamp = dt.datetime.fromisoformat(row["DATE"])
        stamp = stamp.replace(tzinfo=dt.UTC) if stamp.tzinfo is None else stamp.astimezone(dt.UTC)
        if not START <= stamp < END:
            continue  # held January-UTC input; exact pilot selection remains explicit
        if row["REPORT_TYPE"] not in ("FM-15", "FM-16"):
            continue
        if row["CALL_SIGN"].strip() != "KDEN":
            raise ValueError("Historical aviation station/call-sign mapping mismatch")
        for variable, field in zip(VARIABLES, ("TMP", "WND", "VIS"), strict=True):
            value, status = decode(variable, row[field])
            grouped.setdefault((stamp.isoformat(), variable), []).append(
                {
                    "value": value,
                    "status": status,
                    "raw": row[field],
                    "source_sha256": source_sha,
                    "source_row": ordinal,
                    "report_type": row["REPORT_TYPE"],
                }
            )
    result = []
    for (stamp, variable), reports in sorted(grouped.items()):
        good = {r["value"] for r in reports if r["status"] == "accepted"}
        if len(good) > 1:
            raise ValueError("Conflicting accepted station/time/variable measurements")
        chosen = next((r for r in reports if r["status"] == "accepted"), reports[0])
        result.append(
            {
                "station": STATION,
                "observed_at": stamp,
                "variable": variable,
                "value": chosen["value"],
                "status": chosen["status"],
                "duplicate_count": len(reports),
                "provenance": reports,
            }
        )
    return result


def prepare_weather(sources, output):
    """Explicit [(path, expected checksum)] imports; original files remain preserved."""
    output = Path(output)
    if output.exists() or not 1 <= len(sources) <= 2:
        raise ValueError("Weather requires create-only output and one/two bounded imports")
    rows, identities = [], []
    for path, expected in sources:
        path = Path(path)
        if path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError("Weather input exceeds the five-MiB per-file envelope")
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if checksum != expected:
            raise ValueError("Weather source checksum mismatch")
        identities.append(checksum)
        with path.open(newline="") as stream:
            rows.extend(parse_observations(stream, checksum))
    keys = [(r["observed_at"], r["variable"]) for r in rows]
    if not rows or len(rows) > 10000 or len(set(keys)) != len(keys):
        raise ValueError("Empty/oversized weather or overlapping input windows")
    payload = "".join(
        json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n"
        for r in sorted(rows, key=lambda r: (r["observed_at"], r["variable"]))
    )
    timezone_hash = hashlib.sha256(
        Path("/usr/share/zoneinfo/America/Denver").read_bytes()
    ).hexdigest()
    manifest = {
        "contract": CONTRACT,
        "sources": identities,
        "rows": len(rows),
        "mapping_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
        "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
        "timezone_sha256": timezone_hash,
        "timezone": "America/Denver",
        "station": STATION,
        "origin_id": 11292,
        "origin_sequence": "1129202",
        "start": START.isoformat(),
        "end": END.isoformat(),
    }
    manifest["weather_id"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    output.mkdir(parents=True)
    (output / "observations.jsonl").write_text(payload)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def read_weather(path):
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    claimed = manifest.pop("weather_id")
    actual = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    manifest["weather_id"] = claimed
    if actual != claimed or not re.fullmatch(r"[a-f0-9]{64}", claimed):
        raise ValueError("Incompatible or corrupt weather dependency")
    weather_scope(manifest)
    limits = weather_limits(manifest)
    if (path / "observations.jsonl").stat().st_size > limits["bytes"]:
        raise ValueError("Weather payload exceeds measured input bound")
    digest, payload_bytes, rows = hashlib.sha256(), 0, []
    with (path / "observations.jsonl").open("rb") as stream:
        for raw in stream:
            payload_bytes += len(raw)
            if payload_bytes > limits["bytes"] or len(rows) >= limits["observations"]:
                raise ValueError("Weather payload exceeds measured input bound")
            digest.update(raw)
            rows.append(raw.decode().removesuffix("\n"))
    if digest.hexdigest() != manifest["payload_sha256"]:
        raise ValueError("Incompatible or corrupt weather dependency")
    if len(rows) != manifest["rows"] or not 0 < len(rows) <= limits["observations"]:
        raise ValueError("Weather row count mismatch")
    if manifest["contract"] == GHCNH_CONTRACT:
        from airline_warehouse.ghcnh import MAX_PAYLOAD_BYTES, MAX_ROWS

        if (
            payload_bytes != manifest["payload_bytes"]
            or payload_bytes > MAX_PAYLOAD_BYTES
            or len(rows) > MAX_ROWS
        ):
            raise ValueError("GHCNh payload identity/size mismatch")
        start, end = (dt.datetime.fromisoformat(manifest[k]) for k in ("start", "end"))
        for record in rows:
            row = json.loads(record)
            stamp = dt.datetime.fromisoformat(row["observed_at"])
            if (
                row["station"] != manifest["station"]
                or stamp.tzinfo is None
                or not start <= stamp < end
                or row["variable"] not in VARIABLES
                or not isinstance(row["provenance"], list)
                or not row["provenance"]
                or row["duplicate_count"] != len(row["provenance"])
                or (
                    row["status"] == "accepted"
                    and (type(row["value"]) not in (int, float) or not math.isfinite(row["value"]))
                )
            ):
                raise ValueError("Invalid expanded weather observation")
        observation_index(rows)
        validate_v2_records(manifest, rows)
    return manifest, rows


def load_weather(connection, path):
    """Create-only small reference input; exact content comparison on replay."""
    manifest, rows = read_weather(path)
    limit = weather_limits(manifest)["observations"] + 1
    table = "AIRLINE_DB.RAW.WEATHER_" + manifest["weather_id"][:32].upper()
    with connection.cursor() as cur:
        cur.execute(
            f"CREATE TRANSIENT TABLE IF NOT EXISTS {table} (record VARCHAR NOT NULL) "
            "DATA_RETENTION_TIME_IN_DAYS=0"
        )
        cur.execute(f"SELECT record FROM {table} LIMIT {limit}")
        existing = [r[0] for r in cur.fetchall()]
        if not existing:
            cur.execute("BEGIN TRANSACTION")
            try:
                for start in range(0, len(rows), 200):
                    batch = rows[start : start + 200]
                    cur.execute(
                        f"INSERT INTO {table} SELECT column1 FROM VALUES "
                        + ",".join(["(%s)"] * len(batch)),
                        batch,
                    )
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise
            cur.execute(f"SELECT record FROM {table} LIMIT {limit}")
            existing = [r[0] for r in cur.fetchall()]
        if sorted(existing) != sorted(rows):
            raise ValueError("Existing weather input is incomplete or incompatible; no overwrite")
    return manifest, table


def render_weather_sql(name, schema, manifest=None):
    """Same versioned dbt definitions, rebound only to the frozen allowlisted set."""
    from jinja2 import Environment, StrictUndefined

    if name not in ("weather_observations", "den_weather", "weather_integrity"):
        raise ValueError("Unknown weather SQL contract")
    if not re.fullmatch(r"(?:WORK|RELEASE)_[A-F0-9]{24}", schema):
        raise ValueError("Unknown isolated schema")
    root = Path(__file__).resolve().parents[2] / "dbt"
    folder = "tests" if name == "weather_integrity" else "models"
    variables = weather_variables(manifest) if manifest is not None else {"weather_enabled": True}
    return (
        Environment(undefined=StrictUndefined)
        .from_string((root / folder / (name + ".sql")).read_text())
        .render(
            config=lambda **kw: "",
            var=lambda name, default=None: variables.get(name, default),
            ref=lambda n: f"AIRLINE_DB.{schema}.{n.upper()}",
            source=lambda *a: (
                f"(SELECT preserved_record AS record FROM AIRLINE_DB.{schema}.WEATHER_OBSERVATIONS)"
            ),
        )
    )


def observation_index(records):
    """Independent oracle input; sorted once, never SQL/asof implementation reuse."""
    grouped = {v: [] for v in VARIABLES}
    keys = set()
    for record in records:
        row = json.loads(record) if isinstance(record, str) else record
        variable = row["variable"]
        stamp = dt.datetime.fromisoformat(row["observed_at"])
        if stamp.tzinfo is None:
            raise ValueError("Observation lacks explicit UTC identity")
        stamp = stamp.astimezone(dt.UTC)
        key = (row["station"], variable, stamp)
        if key in keys:
            raise ValueError("Duplicate oracle observation")
        keys.add(key)
        if row["status"] == "accepted":
            grouped[variable].append((stamp, row["value"]))
    result = {}
    for variable, rows in grouped.items():
        rows.sort(key=lambda r: r[0])
        result[variable] = ([r[0] for r in rows], [r[1] for r in rows])
    return result


def validate_v2_records(manifest, records):
    """Re-decode preserved GHCNh fields, not the claimed normalized values."""
    from airline_warehouse.ghcnh import (
        BASE_URL,
        MAX_PAYLOAD_BYTES,
        MAX_ROWS,
        MAX_SOURCE_ROWS,
        SOURCE_SIZES,
        decode,
    )
    from airline_warehouse.ghcnh import (
        VARIABLES as FIELDS,
    )
    from airline_warehouse.weather_contract import reference

    if (
        not 0 < len(records) <= MAX_ROWS
        or len(records) != manifest["rows"]
        or not 0 < manifest["payload_bytes"] <= MAX_PAYLOAD_BYTES
    ):
        raise ValueError("GHCNh frozen input bounds mismatch")
    sources = manifest.get("sources", [])
    if not isinstance(sources, list) or sorted(s.get("year", 0) for s in sources) != [
        2023,
        2024,
        2025,
        2026,
    ]:
        raise ValueError("Incomplete GHCNh source identities")
    identities = {}
    pinned_sources = reference()["source_objects"]
    for source in sources:
        year = source["year"]
        sha = source.get("sha256", "")
        pinned = pinned_sources[str(year)]
        if (
            not re.fullmatch(r"[a-f0-9]{64}", sha)
            or sha != pinned["sha256"]
            or source.get("validators") != {k: v for k, v in pinned.items() if k != "sha256"}
            or source.get("url") != f"{BASE_URL}/{year}/psv/GHCNh_USW00003017_{year}.psv"
            or source.get("kind") != ("initial_byte_range" if year == 2026 else "annual_psv")
            or type(source.get("bytes")) is not int
            or not 0 < source["bytes"] <= SOURCE_SIZES[year]
            or (year != 2026 and source["bytes"] != SOURCE_SIZES[year])
        ):
            raise ValueError("Invalid GHCNh source identity")
        identities[sha] = year
    for record in records:
        row = json.loads(record) if isinstance(record, str) else record
        stamp = dt.datetime.fromisoformat(row["observed_at"])
        if (
            row["station"] != manifest["station"]
            or stamp.tzinfo is None
            or not dt.datetime.fromisoformat(manifest["start"])
            <= stamp
            < dt.datetime.fromisoformat(manifest["end"])
            or row["variable"] not in VARIABLES
        ):
            raise ValueError("GHCNh observation scope mismatch")
        variable = row["variable"]
        field = FIELDS[variable]
        reports = row["provenance"]
        if not reports or row["duplicate_count"] != len(reports):
            raise ValueError("GHCNh provenance count mismatch")
        for report in reports:
            if (
                identities.get(report["source_sha256"]) != stamp.year
                or type(report["source_row"]) is not int
                or not 1 <= report["source_row"] <= MAX_SOURCE_ROWS
            ):
                raise ValueError("GHCNh source provenance mismatch")
            original = {field: report["raw"], "REM": report["remarks"]}
            for suffix, key in (
                ("Measurement_Code", "measurement_code"),
                ("Quality_Code", "quality_code"),
                ("Report_Type", "report_type"),
                ("Source_Code", "source_code"),
                ("Source_Station_ID", "source_station_id"),
            ):
                original[field + "_" + suffix] = report[key]
            if decode(variable, original) != (report["value"], report["status"]):
                raise ValueError("GHCNh preserved field decoding mismatch")
        good = {r["value"] for r in reports if r["status"] == "accepted"}
        if len(good) > 1:
            raise ValueError("Conflicting accepted GHCNh observations")
        chosen = next((r for r in reports if r["status"] == "accepted"), reports[0])
        if (row["value"], row["status"]) != (chosen["value"], chosen["status"]):
            raise ValueError("GHCNh chosen field mismatch")


def oracle_match(index, variable, anchor, anchor_status="resolved"):
    if anchor is None:
        return None, None, None, anchor_status
    stamps, rows = index[variable]
    position = bisect_right(stamps, anchor) - 1
    if position < 0:
        return None, None, None, "no_prior_accepted"
    stamp, value = stamps[position], rows[position]
    age = int((anchor - stamp).total_seconds())
    return stamp, age, value if age <= 3600 else None, "matched" if age <= 3600 else "stale"


def validate_frozen_weather(connection, schema, manifest):
    """Complete input digest, field reconstruction, backward join and all-row gates."""
    scope = weather_scope(manifest)
    identity = {k: v for k, v in manifest.items() if k != "weather_id"}
    if hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest() != manifest.get(
        "weather_id"
    ):
        raise ValueError("Corrupt weather dependency identity")
    limits = weather_limits(manifest)
    if not re.fullmatch(r"(?:WORK|RELEASE)_[A-F0-9]{24}", schema):
        raise ValueError("Unknown isolated schema")
    prefix = f"AIRLINE_DB.{schema}."
    with connection.cursor() as cur:
        cur.execute(
            f"SELECT preserved_record FROM {prefix}WEATHER_OBSERVATIONS "
            f"LIMIT {limits['observations'] + 1}"
        )
        records = [r[0] for r in cur.fetchall()]
        ordered = sorted(
            records, key=lambda r: (json.loads(r)["observed_at"], json.loads(r)["variable"])
        )
        digest, payload_bytes = hashlib.sha256(), 0
        for record in ordered:
            encoded = (record + "\n").encode()
            payload_bytes += len(encoded)
            digest.update(encoded)
        if (
            len(records) != manifest["rows"]
            or not 0 < len(records) <= limits["observations"]
            or payload_bytes > limits["bytes"]
            or digest.hexdigest() != manifest["payload_sha256"]
        ):
            raise ValueError("Frozen weather input provenance/checksum mismatch")
        if manifest["contract"] == GHCNH_CONTRACT:
            if payload_bytes != manifest["payload_bytes"]:
                raise ValueError("Frozen weather payload size mismatch")
            validate_v2_records(manifest, records)
        for model in ("weather_observations", "den_weather"):
            expected = render_weather_sql(model, schema, manifest)
            cur.execute(
                f"WITH expected AS ({expected}) "
                f"SELECT * FROM (SELECT * FROM {prefix}{model.upper()} "
                "MINUS SELECT * FROM expected) "
                "UNION ALL SELECT * FROM (SELECT * FROM expected "
                f"MINUS SELECT * FROM {prefix}{model.upper()})"
            )
            if cur.fetchone() is not None:
                raise ValueError("Frozen weather field/match reconstruction failed")
        cur.execute(render_weather_sql("weather_integrity", schema, manifest))
        if cur.fetchone() is not None:
            raise ValueError("Frozen weather population/coverage gate failed")
        expanded = manifest["contract"] == GHCNH_CONTRACT
        extra = ",anchor_status,source_origin_sequence" if expanded else ""
        if expanded:
            extra += ",cancelled,diverted" + "".join(
                f",{v}_observed_at,{v}_age_seconds,{v}_value,{v}_match_status" for v in VARIABLES
            )
        cur.execute(
            f"SELECT source_date,source_clock,scheduled_utc{extra} FROM {prefix}DEN_WEATHER "
            f"LIMIT {limits['flights'] + 1}"
        )
        index = observation_index(records) if expanded else None
        diagnostics = {}
        population = 0

        def anchor_rows():
            while batch := cur.fetchmany(1000):
                yield from batch

        for row in anchor_rows():
            population += 1
            if population > limits["flights"]:
                raise ValueError("Unexpected weather population bound")
            date, clock, actual = row[:3]
            expected, status = classified_anchor(date, clock, manifest, _scope=scope)
            if expanded and (row[3] != status or row[4] not in ("1129202", "1129203")):
                raise ValueError("Frozen anchor classification/mapping failed")
            actual = actual.replace(tzinfo=dt.UTC) if actual is not None else None
            if actual != expected:
                raise ValueError("Frozen anchor differs from pinned America/Denver timezone")
            if expanded:
                for i, variable in enumerate(VARIABLES):
                    offset = 7 + 4 * i
                    stamp, age, value, match_status = row[offset : offset + 4]
                    stamp = stamp.replace(tzinfo=dt.UTC) if stamp is not None else None
                    if (stamp, age, value, match_status) != oracle_match(
                        index, variable, expected, status
                    ):
                        raise ValueError("Frozen match differs from independent backward oracle")
                    key = (date[:7], variable, row[5], row[6], status, match_status)
                    diagnostics[key] = diagnostics.get(key, 0) + 1
        if population == 0:
            raise ValueError("Unexpected empty weather population")
        if expanded:
            # Includes zero-schedule months: missing interior source months cannot
            # silently disappear from the reconciliation report.
            months = [f"{y}-{m:02d}" for y in range(2023, 2026) for m in range(1, 13)]
            return {
                "months": months,
                "scheduled_rows": population,
                "groups": [
                    dict(
                        month=k[0],
                        variable=k[1],
                        cancelled=k[2],
                        diverted=k[3],
                        anchor_status=k[4],
                        match_status=k[5],
                        scheduled_rows=count,
                    )
                    for k, count in sorted(diagnostics.items())
                ],
            }
